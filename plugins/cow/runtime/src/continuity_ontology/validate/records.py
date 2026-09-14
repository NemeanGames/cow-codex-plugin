"""Validate persisted typed bodies, allowing only the declared record envelope."""
from typing import Any, Mapping
from ..model.metamodel import load_metamodel
from .validator import RecordValidator


def validate_persisted(record: Mapping[str, Any]) -> None:
    model = load_metamodel()
    kind = record['recordType']
    entity = model.entities.get(kind)
    envelope = set(model.record_envelope['fields'])
    body = {k: v for k, v in record.items() if k not in envelope or (entity and k in entity.fields)}
    validation = RecordValidator(model).validate(kind, body, with_envelope=False)
    if not validation.ok:
        raise ValueError('invalid persisted ' + kind + ': ' + repr(validation.issues))
