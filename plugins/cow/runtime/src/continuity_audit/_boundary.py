"""The auditor's import boundary, declared as data so it can be tested.

Independence here is not a naming convention. ``tests/security/test_import_boundary.py``
parses every module under ``continuity_audit`` and fails if any of them imports
something outside :data:`ALLOWED_IMPORT_PREFIXES`, so a future edit that reaches
for the producer's evaluation code breaks the build rather than quietly
producing a recomputation that agrees with the producer by construction.

What the auditor may share is declared openly in
:data:`COMMON_MODE_DEPENDENCIES`. Sharing a canonicalizer is a real common-mode
risk: if that serializer is wrong, producer and auditor are wrong together. The
mitigation is that the shared primitives have their own golden vectors, tested
independently of both, and the risk is named in every audit result rather than
left implicit.
"""

from __future__ import annotations

__all__ = [
    "ALLOWED_IMPORT_PREFIXES",
    "FORBIDDEN_IMPORT_PREFIXES",
    "COMMON_MODE_DEPENDENCIES",
    "AUDITOR_ROLE",
]

AUDITOR_ROLE = "independent-auditor"

#: The auditor may import the standard library, the CityQA primitives it shares
#: with the producer, and the digest-profile registry. Nothing else.
ALLOWED_IMPORT_PREFIXES: tuple[str, ...] = (
    "continuity_audit",
    "continuity_ontology.canonical",
    "cityqa.engine.canonical",
    "cityqa.engine.hashing",
    "cityqa.engine.atomic",
    "cityqa.engine.statuses",
    "cityqa.engine.evidence",
)

#: Producer modules that decide anything. Importing one of these would make the
#: auditor's "recomputation" a re-execution of the producer's own logic.
FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "continuity_ontology.claims",
    "continuity_ontology.metrics",
    "continuity_ontology.equivalence",
    "continuity_ontology.checkpoints",
    "continuity_ontology.trace",
    "continuity_ontology.resources",
    "continuity_ontology.projection",
    "continuity_ontology.migration",
    "continuity_ontology.cli",
    "continuity_integrations",
    "cityqa.probes",
    "cityqa.orchestration",
    "cityqa_promote",
)

#: Declared shared primitives, with the risk each one carries.
COMMON_MODE_DEPENDENCIES: tuple[dict[str, str], ...] = (
    {
        "dependency": "cityqa.engine.canonical",
        "sharedWith": "producer",
        "risk": "a canonicalization defect would affect producer and auditor identically",
        "mitigation": "candidate-owned pinned vectors in tests/golden/canonical_bytes.json mitigate shared-canonicalizer drift; they are not independent SFD source admission",
    },
    {
        "dependency": "continuity_ontology.canonical.profiles",
        "sharedWith": "producer",
        "risk": "a wrong digest domain would be wrong on both sides",
        "mitigation": "candidate-owned tests/golden/canonical_bytes.json and tests/golden/sfd_checksum_v1.json plus explicit coincident-domain witnesses; R31 remains qualified",
    },
    {
        "dependency": "cityqa.engine.atomic",
        "sharedWith": "producer",
        "risk": "shared write primitives; read-only in the auditor",
        "mitigation": "the auditor writes only to its own output root and never to the candidate",
    },
)
