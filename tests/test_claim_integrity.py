"""Cycle8 producer consistency regressions; subprocess probes are not an audit."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from continuity_ontology.canonical.profiles import digest_with
from continuity_ontology.checkpoints.claim_integrity import check_claim_integrity, combined_status
from continuity_ontology.checkpoints.store import CheckpointStore, CheckpointError
from continuity_ontology.cli.pipeline import run_end_to_end

REPO = Path(__file__).resolve().parents[1] / "plugins/cow/runtime"

def cli(root, *args):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(REPO / p) for p in ('src', 'third_party/cityqa-deterministic/src')))
    p = subprocess.run([sys.executable, '-m', 'continuity_ontology.cli.main', *args], cwd=root, env=env, capture_output=True, text=True)
    if args[:2] == ('task', 'record'):
        return p.returncode, p.stdout + p.stderr
    return p.returncode, json.loads(p.stdout)

def write(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')

def reseal(value):
    value['revisionId'] = digest_with('continuity.core.v2', value)
    return value

@pytest.fixture
def task(tmp_path):
    (tmp_path / 'a').write_text('same')
    (tmp_path / 'b').write_text('same')
    code, _ = cli(tmp_path, 'task', 'record', '--root', 'run', '--task-id', 'x', '--evidence', 'a::source', '--evidence', 'b')
    assert code == 0
    return tmp_path

def probe(root, status, checkpoint='cp.x'):
    rc, report = cli(root, 'resume', '--checkpoint-root', 'run/checkpoints', '--checkpoint-id', checkpoint, '--observed', '{"processId":42}')
    assert rc == (0 if status == 'PASS' else 6), report
    assert report['claimIntegrity']['status'] == status
    rc, report = cli(root, 'task', 'verify', '--root', 'run', '--checkpoint-id', checkpoint)
    assert rc == {'PASS': 0, 'FAIL': 2, 'UNKNOWN': 3, 'ERROR': 4, 'NOT_RUN': 6}[status], report
    assert report['claimIntegrity']['status'] == status
    return report

@pytest.mark.parametrize('mutation', ['missing', 'corrupt', 'invalid_revision', 'proposition', 'resealed_proposition', 'wrong_type', 'duplicate_requirement'])
def test_audit7_mutations(task, mutation):
    path = task / 'run/records/claim.json'
    value = json.loads(path.read_text())
    if mutation == 'missing': path.unlink()
    elif mutation == 'corrupt': path.write_text('{')
    else:
        if mutation == 'invalid_revision': value['revisionId'] = 'invalid'
        if mutation in {'proposition', 'resealed_proposition'}: value['proposition']['statement'] = 'changed'
        if mutation == 'wrong_type': value['recordType'] = 'Evidence'
        if mutation == 'duplicate_requirement': value['requiredEvidence'].append(copy.deepcopy(value['requiredEvidence'][0]))
        if mutation in {'resealed_proposition', 'duplicate_requirement', 'wrong_type'}: reseal(value)
        write(path, value)
    probe(task, 'UNKNOWN' if mutation == 'missing' else 'FAIL')

def test_happy_identical_bytes(task):
    probe(task, 'PASS')

@pytest.mark.parametrize('mutation', ['duplicate_fact', 'conflicting_pin', 'citation', 'duplicate_citation', 'zero_artifacts'])
def test_checkpoint_bindings(task, mutation):
    path = task / 'run/checkpoints/cp.x.checkpoint.json'
    value = json.loads(path.read_text())
    facts = value['snapshot']['requiredFacts']
    if mutation == 'duplicate_fact': facts.append(copy.deepcopy(next(f for f in facts if f['factId'] == 'claimDigest')))
    if mutation == 'conflicting_pin': next(f for f in facts if f['factId'] == 'claimDigest')['value'] = 'sha256:' + '0'*64
    if mutation == 'citation': value['acceptedDecisions'][0]['citedInputs'] = ['sha256:' + '0'*64]
    if mutation == 'duplicate_citation': value['acceptedDecisions'].append(copy.deepcopy(value['acceptedDecisions'][0]))
    if mutation == 'zero_artifacts':
        value['snapshot']['admittedSourceVersions'] = {}
        value['snapshot']['artifactRefs'] = {}
        (task / 'run/records/claim.json').unlink()
    write(path, reseal(value))
    if mutation == 'zero_artifacts':
        rc, report = cli(task, 'resume', '--checkpoint-root', 'run/checkpoints', '--checkpoint-id', 'cp.x', '--observed', '{"processId":42}')
        assert rc == 6 and report['claimIntegrity']['status'] == 'UNKNOWN'
    else: probe(task, 'FAIL')

@pytest.fixture
def bundle(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'a').write_text('input')
    run_end_to_end(tmp_path / 'run', source, ['a'])
    return tmp_path

@pytest.mark.parametrize('mutation', ['none', 'missing_body', 'altered_body', 'duplicate_member', 'missing_member', 'revision_digest', 'member_digest', 'resealed_bundle', 'missing_cas', 'corrupt_cas'])
def test_bundle_probes(bundle, mutation):
    index = bundle / 'run/frozen/bundle.json'
    value = json.loads(index.read_text())
    path = next((bundle / 'run/records/claim-revisions').glob('*.json'))
    revision = json.loads(path.read_text())
    if mutation == 'missing_body': path.unlink()
    if mutation == 'altered_body':
        revision['claim']['proposition']['statement'] = 'changed'
        write(path, revision)
    if mutation == 'duplicate_member': value['memberIndex'].append(copy.deepcopy(value['memberIndex'][0]))
    if mutation == 'missing_member': value['memberIndex'] = []
    if mutation == 'revision_digest':
        revision['revisionNumber'] += 1
        write(path, revision)
    if mutation == 'member_digest': value['memberIndex'][0]['revisionDigest'] = 'sha256:'+'0'*64
    if mutation == 'resealed_bundle':
        value['candidateDigest'] = 'sha256:'+'0'*64
        value['resolvedStateDigest'] = digest_with('continuity.core.v2', {'members': value['memberIndex'], 'candidateDigest': value['candidateDigest']})
    if mutation in {'missing_cas', 'corrupt_cas'}:
        ref = revision['claim']['producerAssertion']['evidenceRefs'][0][7:]
        cas_path = bundle / 'run/cas' / ref[:2] / ref[2:4] / ref
        if mutation == 'missing_cas': cas_path.unlink()
        else: cas_path.write_bytes(b'corrupt')
    write(index, value)
    probe(bundle, 'PASS' if mutation == 'none' else 'UNKNOWN' if mutation == 'missing_body' else 'FAIL', 'cp.e2e')

def test_claim_free_and_zero_artifact_obligation(tmp_path):
    cp = {'snapshot': {}, 'acceptedDecisions': []}
    assert check_claim_integrity(cp, tmp_path, None)['status'] == 'NOT_RUN'
    cp['snapshot']['requiredFacts'] = [{'factId': 'claimDigest', 'present': True, 'value': 'sha256:'+'0'*64}]
    result = check_claim_integrity(cp, tmp_path, None)
    assert result['required'] and result['status'] == 'UNKNOWN'

def test_io_error_and_duplicate_json(task, monkeypatch):
    cp = json.loads((task / 'run/checkpoints/cp.x.checkpoint.json').read_text())
    def denied(*a, **kw): raise PermissionError('test denied')
    with monkeypatch.context() as m:
        m.setattr(Path, 'read_text', denied)
        assert check_claim_integrity(cp, task / 'run/records', None)['status'] == 'ERROR'
    (task / 'run/records/claim.json').write_text('{"recordType":"Claim","recordType":"Claim"}')
    assert check_claim_integrity(cp, task / 'run/records', None)['status'] == 'FAIL'
    assert combined_status('FAIL', 'ERROR', 'UNKNOWN') == 'FAIL'

def test_precommit_preserves_checkpoint(task):
    store = CheckpointStore(task / 'run/checkpoints')
    cp = store.load('cp.x')
    before = (task / 'run/checkpoints/cp.x.checkpoint.json').read_bytes()
    claim = json.loads((task / 'run/records/claim.json').read_text())
    claim['proposition']['statement'] = 'unsealed mutation'
    with pytest.raises(CheckpointError):
        store.commit('cp.x', outcome_id=cp['outcome'], snapshot=cp['snapshot'], last_sealed_event_seq=cp['lastSealedEventSeq'], last_sealed_event_digest=cp['lastSealedEventDigest'], accepted_decisions=cp['acceptedDecisions'], unresolved_claims=cp['unresolvedClaims'], open_operations=[], next_legal_actions=cp['nextLegalActions'], recovery_policy_ref=cp['recoveryPolicyRef'], closure_receipt=cp['closureReceipt'], proposed_claim_records={'claim.json': claim})
    assert (task / 'run/checkpoints/cp.x.checkpoint.json').read_bytes() == before

def test_zero_artifact_valid_claim(task):
    claim_path = task / 'run/records/claim.json'
    claim = json.loads(claim_path.read_text())
    claim['requiredEvidence'] = []
    claim['producerAssertion']['evidenceRefs'] = []
    claim['sufficiency']['requirementResults'] = []
    claim['sufficiency']['mandatoryApplicable'] = 0
    claim['sufficiency']['mandatorySatisfied'] = 0
    write(claim_path, reseal(claim))
    cp_path = task / 'run/checkpoints/cp.x.checkpoint.json'
    cp = json.loads(cp_path.read_text())
    cp['snapshot']['admittedSourceVersions'] = {}
    cp['snapshot']['artifactRefs'] = {}
    cp['closureReceipt']['witnessRefs'] = []
    next(f for f in cp['snapshot']['requiredFacts'] if f['factId'] == 'claimDigest')['value'] = claim['revisionId']
    cp['acceptedDecisions'][0]['citedInputs'] = [claim['revisionId']]
    write(cp_path, reseal(cp))
    probe(task, 'PASS')

def test_claim_free_checkpoint_processes(task):
    cp_path = task / 'run/checkpoints/cp.x.checkpoint.json'
    cp = json.loads(cp_path.read_text())
    cp['snapshot']['requiredFacts'] = []
    cp['snapshot']['admittedSourceVersions'] = {}
    cp['snapshot']['artifactRefs'] = {}
    cp['acceptedDecisions'] = []
    write(cp_path, reseal(cp))
    rc, report = cli(task, 'resume', '--checkpoint-root', 'run/checkpoints', '--checkpoint-id', 'cp.x', '--observed', '{"processId":42}')
    assert rc == 0 and report['claimIntegrity']['required'] is False
    rc, report = cli(task, 'task', 'verify', '--root', 'run')
    assert rc == 6 and report['status'] == 'NOT_RUN'

def test_required_claim_no_cas(task):
    import shutil
    shutil.rmtree(task / 'run/cas')
    report = probe(task, 'NOT_RUN')
    assert report['evidenceIntegrity']['status'] == 'NOT_RUN'

def test_conflicting_requirements_before_publish(task):
    from continuity_ontology.claims.bundle import compile_claim, ClaimError
    req = {'requirementId': 'r.same', 'evidenceKind': 'file'}
    with pytest.raises(ClaimError, match='duplicate'):
        compile_claim('c.x', {'claimType': 'HASH_EQUALITY', 'scope': {}}, {'producerStatus': 'PASS'}, [req, req], {})


def test_body_io_error_processes(task):
    path = task / 'run/records/claim.json'
    path.unlink()
    path.mkdir()
    probe(task, 'ERROR')

def test_evaluation_error(bundle, monkeypatch):
    import continuity_ontology.checkpoints.claim_integrity as checker
    cp = json.loads((bundle / 'run/checkpoints/cp.e2e.checkpoint.json').read_text())
    def unavailable(*args): raise RuntimeError('evaluation unavailable')
    monkeypatch.setattr(checker, 'digest_with', unavailable)
    assert checker.check_claim_integrity(cp, bundle / 'run/records', None)['status'] == 'ERROR'


def test_recording_cannot_replace_committed_bundle(bundle):
    root = bundle / 'run'
    before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with pytest.raises(ValueError, match='already contains a checkpoint'):
        run_end_to_end(root, bundle / 'source', ['missing'])
    assert {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()} == before


def test_nested_claim_wrong_type_consistent_bundle(bundle):
    index = bundle / 'run/frozen/bundle.json'
    value = json.loads(index.read_text())
    old = next((bundle / 'run/records/claim-revisions').glob('*.json'))
    revision = json.loads(old.read_text())
    revision['claim']['recordType'] = 'Evidence'
    digest = digest_with('continuity.core.v2', revision)
    write(old.parent / (digest[7:] + '.json'), revision)
    value['memberIndex'][0]['revisionDigest'] = digest
    value['resolvedStateDigest'] = digest_with('continuity.core.v2', {'members': value['memberIndex'], 'candidateDigest': value['candidateDigest']})
    write(index, value)
    cp_path = bundle / 'run/checkpoints/cp.e2e.checkpoint.json'
    cp = json.loads(cp_path.read_text())
    next(f for f in cp['snapshot']['requiredFacts'] if f['factId'] == 'bundleDigest')['value'] = value['resolvedStateDigest']
    write(cp_path, reseal(cp))
    probe(bundle, 'FAIL', 'cp.e2e')
    store = CheckpointStore(bundle / 'run/checkpoints')
    with pytest.raises(CheckpointError):
        store.commit('cp.invalid', outcome_id=cp['outcome'], snapshot=cp['snapshot'], last_sealed_event_seq=cp['lastSealedEventSeq'], last_sealed_event_digest=cp['lastSealedEventDigest'], accepted_decisions=cp['acceptedDecisions'], unresolved_claims=[], open_operations=[], next_legal_actions=cp['nextLegalActions'], recovery_policy_ref=cp['recoveryPolicyRef'], closure_receipt=cp['closureReceipt'])
