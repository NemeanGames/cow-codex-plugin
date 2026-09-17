"""Build deterministic Codex and Claude marketplace archives from public files."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins/cow'

def public_files(root):
    return [p for p in sorted(root.rglob('*'), key=lambda p: p.relative_to(root).as_posix()) if p.is_file()
            and '__pycache__' not in p.parts and p.suffix != '.pyc']

def runtime_manifest():
    return ''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' +
                   p.relative_to(PLUGIN).as_posix() + '\n'
                   for p in public_files(PLUGIN / 'runtime'))

def build(out):
    if out.resolve() == PLUGIN.resolve() or PLUGIN.resolve() in out.resolve().parents:
        raise ValueError('Archive output must be outside the plugin source tree')
    recorded = (PLUGIN / 'RUNTIME_MANIFEST.sha256').read_text(encoding='utf-8')
    if recorded != runtime_manifest():
        raise ValueError('Public runtime differs from RUNTIME_MANIFEST.sha256')
    out.mkdir(parents=True, exist_ok=True)
    receipts = []
    for client, metadata in [('codex', '.codex-plugin'), ('claude', '.claude-plugin')]:
        version = json.loads((PLUGIN / metadata / 'plugin.json').read_text())['version']
        stem = f'cow-{client}-marketplace-v{version}'
        files = {name: ROOT / name for name in ('LICENSE','README.md','CHANGELOG.md')}
        marketplace = '.agents/plugins/marketplace.json' if client == 'codex' else '.claude-plugin/marketplace.json'
        files[marketplace] = ROOT / marketplace
        for path in public_files(PLUGIN):
            relative = path.relative_to(PLUGIN)
            if relative.parts[0] == ('.claude-plugin' if client == 'codex' else '.codex-plugin'):
                continue
            files['plugins/cow/' + relative.as_posix()] = path
        archive = out / (stem + '.zip')
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, path in sorted(files.items()):
                info = zipfile.ZipInfo(stem + '/' + name, (2026, 1, 1, 0, 0, 0))
                info.create_system = 3  # fixed archive metadata on every build host
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                z.writestr(info, path.read_bytes())
        receipts.append({'file':archive.name, 'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(), 'members':len(files)})
    (out / 'SHA256SUMS').write_text(''.join(r['sha256']+'  '+r['file']+'\n' for r in receipts), encoding='utf-8', newline='\n')
    return receipts

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--refresh-runtime-manifest', action='store_true')
    args = parser.parse_args()
    if args.refresh_runtime_manifest:
        (PLUGIN / 'RUNTIME_MANIFEST.sha256').write_text(runtime_manifest(), encoding='utf-8', newline='\n')
    print(json.dumps(build(args.out), indent=2))
