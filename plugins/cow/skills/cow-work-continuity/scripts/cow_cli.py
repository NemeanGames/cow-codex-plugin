#!/usr/bin/env python3
from __future__ import annotations
import sys, os, json, hashlib
from pathlib import Path
sys.dont_write_bytecode = True
def main():
    root = Path(__file__).resolve().parents[3] / "runtime"
    sys.path[:0] = [str(root / "src"), str(root / "third_party/cityqa-deterministic/src")]
    os.environ["ONT20_METAMODEL"] = str(root / "ontology/metamodel.json")
    try:
        from continuity_ontology.model.metamodel import load_metamodel
        from continuity_ontology.generate.generators import generate_all, artifact_bytes
        model = load_metamodel(root / "ontology/metamodel.json")
        manifest = json.loads((root / "ontology/generated/GENERATION_MANIFEST.json").read_text())
        if model.digest != manifest["semanticModelDigest"] or model.extension_digests != manifest["extensionDigests"]:
            raise ValueError("semantic model or extension digest mismatch")
        generated = {k:v for k,v in generate_all(model).items() if not k.startswith("_")}
        if set(generated) != set(manifest["files"]):
            raise ValueError("generated file inventory mismatch")
        for rel, expected in manifest["files"].items():
            data = (root / rel).read_bytes()
            if "sha256:" + hashlib.sha256(data).hexdigest() != expected or data != artifact_bytes(generated[rel]):
                raise ValueError("generated artifact mismatch: " + rel)
    except Exception as exc:
        print(json.dumps({"status":"ERROR", "reason":"runtime identity check failed: " + str(exc)}))
        return 4
    from continuity_ontology.cli.main import main as cli
    return int(cli(sys.argv[1:]))
if __name__ == "__main__":
    raise SystemExit(main())
