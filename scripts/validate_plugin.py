#!/usr/bin/env python3
from __future__ import annotations
import json, re, sys
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
REQ_INTERFACE = {"displayName","shortDescription","longDescription","developerName","category","capabilities"}
ALLOWED_TOP = {"name","version","description","author","homepage","repository","license","keywords","skills","mcpServers","apps","interface"}

def die(msg):
    print('[ERROR]', msg); raise SystemExit(1)

def main():
    p = Path(sys.argv[1]).resolve()
    mf = p/'.codex-plugin/plugin.json'
    if not mf.exists(): die('missing .codex-plugin/plugin.json')
    data = json.loads(mf.read_text(encoding='utf-8'))
    extra = set(data)-ALLOWED_TOP
    if extra: die('unsupported top-level fields: '+', '.join(sorted(extra)))
    for k in ('name','version','description','author','interface'):
        if k not in data: die('missing '+k)
    if data['name'] != p.name: die('plugin folder name must match manifest name')
    cm = p/'.claude-plugin/plugin.json'
    if cm.exists():
        claude = json.loads(cm.read_text(encoding='utf-8'))
        if claude.get('name') != p.name: die('Claude plugin name mismatch')
        if not SEMVER.match(claude.get('version','')): die('invalid Claude plugin version')
        if not (p/claude.get('skills','skills')).is_dir(): die('Claude skills path missing')
        market = p.parents[1]/'.claude-plugin/marketplace.json'
        entries = json.loads(market.read_text(encoding='utf-8'))
        if entries.get('name') != 'cow-claude': die('unexpected Claude marketplace identifier')
        if entries.get('plugins',[]) != [{'name':'cow','source':'./plugins/cow','description':'Evidence-bound offline work continuity.'}]:
            die('unexpected Claude marketplace source')
    if not NAME_RE.match(data['name']): die('invalid plugin name')
    if not SEMVER.match(data['version']): die('version is not strict semver')
    if not isinstance(data['author'],dict) or not data['author'].get('name'): die('author.name required')
    missing = REQ_INTERFACE-set(data['interface'])
    if missing: die('missing interface fields: '+', '.join(sorted(missing)))
    if 'skills' in data:
        s = p/data['skills']
        if not s.exists(): die('skills path does not exist')
    for field in ('composerIcon','logo','logoDark'):
        v = data['interface'].get(field)
        if v and not (p/v).exists(): die(f'{field} does not exist: {v}')
    for skill in (p/'skills').glob('*'):
        if not skill.is_dir(): continue
        sm = skill/'SKILL.md'
        oy = skill/'agents/openai.yaml'
        if not sm.exists(): die(f'{skill.name}: missing SKILL.md')
        text = sm.read_text(encoding='utf-8')
        if '[TODO' in text: die(f'{skill.name}: TODO placeholder')
        if not text.startswith('---\n') or 'name:' not in text.split('---',2)[1] or 'description:' not in text.split('---',2)[1]: die(f'{skill.name}: invalid frontmatter')
        if not oy.exists(): die(f'{skill.name}: missing agents/openai.yaml')
    print('[OK] plugin structure validates:', p)

if __name__=='__main__': main()
