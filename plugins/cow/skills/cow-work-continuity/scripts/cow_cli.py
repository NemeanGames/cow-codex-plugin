#!/usr/bin/env python3
from __future__ import annotations
import os, sys
from pathlib import Path

def runtime_root() -> Path:
    return Path(__file__).resolve().parents[3] / "runtime"

def main() -> int:
    root = runtime_root()
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "third_party" / "cityqa-deterministic" / "src"))
    os.environ.setdefault("ONT20_METAMODEL", str(root / "ontology" / "metamodel.json"))
    from continuity_ontology.cli.main import main as cow_main
    return int(cow_main(sys.argv[1:]))

if __name__ == "__main__":
    raise SystemExit(main())
