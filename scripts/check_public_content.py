"""Check distributable files for private host paths and common secret formats."""
from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'windows_user_path': re.compile(r'[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z0-9_-]+'),
    'posix_user_path': re.compile(r'/(?:home|Users)/[A-Za-z0-9_-]+/'),
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'github_token': re.compile(r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}'),
    'private_project': re.compile(r'CitySample_' + r'Pershing|pershing/osm/way-\d+|\bL_City_\d{3}\b'),
}

def main():
    names = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'], cwd=ROOT).decode().split('\0')
    findings=[]
    for name in sorted(set(filter(None,names))):
        path=ROOT/name
        if not path.is_file(): continue
        if set(path.relative_to(ROOT).parts) & {'source_snapshots','audit_out','.cow'} or path.suffix == '.bundle':
            findings.append({'file':name,'issue':'private path'})
        text=path.read_bytes().decode('utf-8',errors='replace')
        for kind,pattern in PATTERNS.items():
            if pattern.search(text): findings.append({'file':name,'issue':kind})
    print(json.dumps({'status':'FAIL' if findings else 'PASS','findings':findings},indent=2))
    return int(bool(findings))

if __name__=='__main__': raise SystemExit(main())
