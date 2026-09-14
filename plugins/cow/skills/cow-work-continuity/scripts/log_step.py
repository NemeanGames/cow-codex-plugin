#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, time
from pathlib import Path

PURPOSES = ("PLANNING","RETRIEVAL","GENERATION","VERIFICATION","AUDIT","PACKAGING","RECOVERY_REWORK")
STATUSES = ("PASS","FAIL","UNKNOWN","ERROR","NOT_RUN")

def main() -> int:
    p = argparse.ArgumentParser(description="Append one deterministic COW step event.")
    p.add_argument("--file", default=".cow/steps.jsonl")
    p.add_argument("--step", required=True)
    p.add_argument("--purpose", choices=PURPOSES, default="GENERATION")
    p.add_argument("--status", choices=STATUSES, default="PASS")
    args = p.parse_args()
    path = Path(args.file)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"step": args.step, "t_ns": time.monotonic_ns(), "purpose": args.purpose, "status": args.status}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(row, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
