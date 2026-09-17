"""Exercise shipped wrappers from fresh marketplace archives, not upstream source."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]

def command(wrapper, cwd, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.pop('ONT20_METAMODEL', None)
    env.pop('PYTHONPATH', None)
    result = subprocess.run([sys.executable, '-B', str(wrapper), *args], cwd=cwd,
                            env=env, capture_output=True, text=True)
    return result.returncode, result.stdout

@pytest.mark.parametrize('client', ['codex','claude'])
def test_fresh_archive_workflow(tmp_path, client):
    subprocess.run([sys.executable, '-B', str(ROOT/'scripts/build_plugins.py'), '--out', str(tmp_path/'z')], check=True, capture_output=True)
    archive = next((tmp_path/'z').glob(f'cow-{client}-*.zip'))
    with zipfile.ZipFile(archive) as z:
        assert len(z.namelist()) == len(set(z.namelist()))
        assert not any('..' in Path(n).parts for n in z.namelist())
        z.extractall(tmp_path/'unpacked')
    plugin = next((tmp_path/'unpacked').iterdir())/'plugins/cow'
    wrapper = plugin/'skills/cow-work-continuity/scripts/cow_cli.py'
    rc, text = command(wrapper, tmp_path, 'model')
    assert rc == 0 and json.loads(text)['kernelComplete']
    (tmp_path/'receipt.json').write_text('{"synthetic":true}')
    (tmp_path/'receipt.py').write_text('# synthetic receipt generator\n')
    rc, text = command(wrapper, tmp_path, 'task','record','--root','run','--task-id','package',
                       '--evidence','receipt.json::source','--evidence','receipt.py','--quiet')
    assert rc == 0, text
    assert text.strip().endswith('hand the claim and its evidence to the independent auditor')
    def verify_resume(root, expected_status, expected_verify, resumable):
        rc, text = command(wrapper, tmp_path,'task','verify','--root',root,'--checkpoint-id','cp.package')
        assert rc == expected_verify and json.loads(text)['status'] == expected_status, text
        rc, text = command(wrapper, tmp_path,'resume','--checkpoint-root',root+'/checkpoints',
                           '--cas-root',root+'/cas','--checkpoint-id','cp.package',
                           '--observed',json.dumps({'processId':os.getpid()}))
        assert rc == (0 if resumable else 6) and json.loads(text)['resumable'] is resumable, text
    verify_resume('run','PASS',0,True)
    shutil.copytree(tmp_path/'run',tmp_path/'missing')
    (tmp_path/'missing/records/claim.json').unlink()
    verify_resume('missing','UNKNOWN',3,False)
    shutil.copytree(tmp_path/'run',tmp_path/'changed')
    claim = tmp_path/'changed/records/claim.json'
    data=json.loads(claim.read_text()); data['proposition']['statement']='changed'
    claim.write_text(json.dumps(data))
    verify_resume('changed','FAIL',2,False)
    # A generated-artifact edit must fail at wrapper startup, before CLI dispatch.
    model_file = plugin/'runtime/ontology/generated/vocabulary.jsonld'
    model_file.write_bytes(model_file.read_bytes()+b' ')
    rc, text=command(wrapper,tmp_path,'model')
    assert rc == 4 and 'runtime identity check failed' in text

def test_two_builds_identical(tmp_path):
    spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build_plugins.py')
    builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    assert builder.build(tmp_path/'first') == builder.build(tmp_path/'second')

def test_manifest_order_is_case_sensitive_posix(tmp_path):
    spec=importlib.util.spec_from_file_location('builder',ROOT/'scripts/build_plugins.py')
    builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    for name in ('z','a','A','B'):
        (tmp_path/name).write_text(name)
    assert [p.name for p in builder.public_files(tmp_path)] == ['A','B','a','z']
