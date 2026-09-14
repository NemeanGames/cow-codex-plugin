"""Run-owned process and lock tracking.

State closure needs to know exactly what a run owns, so this module is the only
place a run-owned process or lock is created. Anything it did not register is
not a run-owned resource, and the closure receipt says so rather than guessing.

Unreal is launched here, and only ever as an argument array. A launch built as
one shell string is how R3.1 happened: the quoting of a project path with a
space silently changed the argument vector, and the run proceeded against a
different project than the one the contract named.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from .canonical import canonical_path
from .hashing import digest_value

__all__ = [
    "ProcessControlError",
    "LaunchRecord",
    "ProcessRegistry",
    "run_argument_vector",
]


class ProcessControlError(RuntimeError):
    """Raised when a launch could not be attempted as specified."""


class LaunchRecord:
    """The exact argument vector used, recorded before launch."""

    __slots__ = ("argv", "cwd", "executable", "returncode", "stdout", "stderr",
                 "launched", "failure")

    def __init__(
        self,
        argv: Sequence[str],
        cwd: str,
        executable: str,
        launched: bool = False,
        returncode: int | None = None,
        stdout: str = "",
        stderr: str = "",
        failure: str | None = None,
    ) -> None:
        self.argv = list(argv)
        self.cwd = cwd
        self.executable = executable
        self.launched = launched
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.failure = failure

    def as_dict(self, include_output: bool = False) -> dict[str, Any]:
        record: dict[str, Any] = {
            "argumentVector": list(self.argv),
            "argumentVectorDigest": digest_value({"argv": list(self.argv)}),
            "workingDirectory": canonical_path(self.cwd),
            "executable": canonical_path(self.executable),
            "launched": self.launched,
            "returnCode": self.returncode,
        }
        if self.failure is not None:
            record["launchFailure"] = self.failure
        if include_output:
            # Transcripts stay out of receipts and worker packets by default.
            record["stdoutDigest"] = digest_value({"text": self.stdout})
            record["stderrDigest"] = digest_value({"text": self.stderr})
        return record

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "LaunchRecord(%r, launched=%r)" % (self.argv[:2], self.launched)


def run_argument_vector(
    argv: Sequence[str],
    cwd: str | Path,
    timeout_seconds: float | None = None,
) -> LaunchRecord:
    """Run a command as an argument array.

    ``shell`` is never enabled. The vector is recorded before the launch so that
    a failed launch still leaves evidence of exactly what was attempted.
    """
    vector = [str(item) for item in argv]
    if not vector:
        raise ProcessControlError("argument vector is empty")
    working_directory = str(cwd)
    record = LaunchRecord(vector, working_directory, vector[0])

    try:
        completed = subprocess.run(
            vector,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            cwd=working_directory,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        record.failure = "executable not found: " + str(exc)
        return record
    except NotADirectoryError as exc:
        record.failure = "working directory not usable: " + str(exc)
        return record
    except subprocess.TimeoutExpired:
        record.failure = "timeout after " + str(timeout_seconds) + "s"
        return record
    except OSError as exc:
        record.failure = "launch failed: " + str(exc)
        return record

    record.launched = True
    record.returncode = completed.returncode
    record.stdout = completed.stdout or ""
    record.stderr = completed.stderr or ""
    return record


class ProcessRegistry:
    """Tracks what one run owns, so state closure can account for all of it."""

    def __init__(self) -> None:
        self._processes: list[dict[str, Any]] = []
        self._locks: list[str] = []
        self._handles: list[Any] = []
        self._temporary: list[str] = []

    # -- registration ---------------------------------------------------

    def register_process(self, pid: int, command_name: str) -> None:
        self._processes.append(
            {"pid": int(pid), "commandName": command_name, "terminationState": "STILL_RUNNING"}
        )

    def register_completed(self, pid: int, command_name: str) -> None:
        self._processes.append(
            {"pid": int(pid), "commandName": command_name, "terminationState": "EXITED"}
        )

    def register_lock(self, lock_id: str) -> None:
        if lock_id not in self._locks:
            self._locks.append(lock_id)

    def register_handle(self, handle: Any) -> None:
        self._handles.append(handle)

    def register_temporary(self, path: str | Path) -> None:
        logical = canonical_path(str(path))
        if logical not in self._temporary:
            self._temporary.append(logical)

    # -- closure --------------------------------------------------------

    def terminate_processes(self, timeout_seconds: float = 5.0) -> list[dict[str, Any]]:
        """Terminate every still-running run-owned process."""
        import signal
        import time

        for entry in self._processes:
            if entry["terminationState"] != "STILL_RUNNING":
                continue
            pid = entry["pid"]
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                entry["terminationState"] = "EXITED"
                continue
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                except OSError:
                    entry["terminationState"] = "TERMINATED"
                    break
                time.sleep(0.05)
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                    entry["terminationState"] = "KILLED"
                except (ProcessLookupError, OSError, AttributeError):
                    # The process is gone, or the platform has no SIGKILL. Either
                    # way it is no longer running under this run's ownership.
                    entry["terminationState"] = "TERMINATED"
        return list(self._processes)

    def release_locks(self) -> list[str]:
        released = list(self._locks)
        for lock_id in released:
            path = Path(lock_id)
            if path.is_file():
                try:
                    path.unlink()
                except OSError:
                    continue
        self._locks.clear()
        return released

    def close_handles(self) -> int:
        closed = 0
        for handle in self._handles:
            close = getattr(handle, "close", None)
            if close is None:
                continue
            try:
                close()
                closed += 1
            except Exception:
                continue
        self._handles.clear()
        return closed

    def remove_temporary(self) -> list[str]:
        removed: list[str] = []
        for logical in list(self._temporary):
            path = Path(logical)
            try:
                if path.is_file():
                    path.unlink()
                    removed.append(logical)
                elif path.is_dir():
                    import shutil

                    shutil.rmtree(path, ignore_errors=True)
                    removed.append(logical)
            except OSError:
                continue
        self._temporary.clear()
        return removed

    # -- inspection -----------------------------------------------------

    @property
    def processes(self) -> list[dict[str, Any]]:
        return list(self._processes)

    @property
    def locks(self) -> list[str]:
        return list(self._locks)

    def still_running(self) -> list[dict[str, Any]]:
        return [
            entry for entry in self._processes
            if entry["terminationState"] == "STILL_RUNNING"
        ]
