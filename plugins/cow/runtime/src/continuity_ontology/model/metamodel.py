"""Load and resolve the single semantic source.

``ontology/metamodel.json`` is the only authored definition of entities,
relations, vocabularies and inference rules. Extensions are separate versioned
documents referenced from it and bound by digest at load time. Everything under
``ontology/generated``, ``schemas/generated`` and ``generated/typescript`` is
produced from this resolved model; none of it is authored.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..canonical.profiles import digest_with

__all__ = [
    "MetamodelError",
    "FieldSpec",
    "EntitySpec",
    "RelationSpec",
    "Metamodel",
    "load_metamodel",
    "default_metamodel_path",
    "KERNEL_CONCEPTS",
]

#: The user-locked minimum kernel. This tuple is the acceptance oracle for R03
#: and is compared against the resolved model, never derived from it.
KERNEL_CONCEPTS: tuple[str, ...] = (
    "Outcome",
    "WorkItem",
    "Capability",
    "Implementation",
    "ExecutionPlan",
    "ExecutionTrace",
    "Artifact",
    "Contract",
    "Gate",
    "Evidence",
    "Decision",
    "Checkpoint",
    "StateSnapshot",
    "ResourceUsage",
    "EfficiencyClaim",
    "EquivalenceContract",
)

_SCALARS = frozenset(
    {
        "string",
        "text",
        "integer",
        "decimal",
        "boolean",
        "timestamp",
        "duration_ms",
        "digest",
        "id",
        "uri",
        "json",
    }
)


class MetamodelError(ValueError):
    """Raised when the semantic source is malformed or internally inconsistent."""


class FieldSpec:
    __slots__ = ("name", "type", "required", "doc")

    def __init__(self, name: str, raw: Mapping[str, Any]) -> None:
        if "type" not in raw:
            raise MetamodelError("field " + name + " has no type")
        self.name = name
        self.type = raw["type"]
        self.required = bool(raw.get("required", False))
        self.doc = raw.get("doc", "")

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type, "required": self.required}
        if self.doc:
            out["doc"] = self.doc
        return out


class EntitySpec:
    __slots__ = ("name", "kind", "doc", "fields", "identity_bearing", "extension_id")

    def __init__(self, name: str, raw: Mapping[str, Any], extension_id: str | None) -> None:
        self.name = name
        self.kind = raw.get("kind", "EXTENSION")
        self.doc = raw.get("doc", "")
        self.extension_id = extension_id
        self.identity_bearing = bool(raw.get("identityBearing", self.kind != "SUPPORT"))
        fields = raw.get("fields")
        if not isinstance(fields, Mapping):
            raise MetamodelError("entity " + name + " has no fields mapping")
        self.fields = {k: FieldSpec(k, v) for k, v in fields.items()}

    def required_field_names(self) -> tuple[str, ...]:
        return tuple(sorted(n for n, f in self.fields.items() if f.required))

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "doc": self.doc,
            "identityBearing": self.identity_bearing,
            "extensionId": self.extension_id,
            "fields": {k: v.as_dict() for k, v in sorted(self.fields.items())},
        }


class RelationSpec:
    __slots__ = (
        "name",
        "domain",
        "range",
        "min_cardinality",
        "max_cardinality",
        "transitive",
        "derived_from_direct",
        "closure_relation",
        "alias_of",
        "typed_per_claim",
        "doc",
    )

    def __init__(self, name: str, raw: Mapping[str, Any]) -> None:
        self.name = name
        self.domain = raw.get("domain")
        self.range = raw.get("range")
        self.min_cardinality = raw.get("minCardinality")
        self.max_cardinality = raw.get("maxCardinality")
        self.transitive = bool(raw.get("transitive", False))
        self.derived_from_direct = raw.get("derivedFromDirect")
        self.closure_relation = raw.get("closureRelation")
        self.alias_of = raw.get("aliasOf")
        self.typed_per_claim = bool(raw.get("typedPerClaim", False))
        self.doc = raw.get("doc", "")

    def as_dict(self) -> dict[str, Any]:
        out = {
            "domain": self.domain,
            "range": self.range,
            "transitive": self.transitive,
        }
        for key, value in (
            ("minCardinality", self.min_cardinality),
            ("maxCardinality", self.max_cardinality),
            ("derivedFromDirect", self.derived_from_direct),
            ("closureRelation", self.closure_relation),
            ("aliasOf", self.alias_of),
            ("doc", self.doc),
        ):
            if value not in (None, "", False):
                out[key] = value
        if self.typed_per_claim:
            out["typedPerClaim"] = True
        return out


class Metamodel:
    """The resolved semantic model."""

    def __init__(self, root: Mapping[str, Any], extensions: list[Mapping[str, Any]], source_path: Path) -> None:
        self.source_path = source_path
        self.root = dict(root)
        self.version = str(root.get("metamodelVersion", ""))
        self.product = str(root.get("product", ""))
        self.product_version = str(root.get("productVersion", ""))
        self.namespace = str(root.get("namespace", ""))
        self.prefix = str(root.get("prefix", "cont"))
        self.vocabularies: dict[str, dict[str, Any]] = dict(root.get("vocabularies", {}))
        self.record_envelope = dict(root.get("recordEnvelope", {}))
        self.inference = dict(root.get("inference", {}))
        self.runtime_policy = dict(root.get("runtimePolicy", {}))

        self.entities: dict[str, EntitySpec] = {}
        for name, raw in root.get("entities", {}).items():
            self.entities[name] = EntitySpec(name, raw, None)

        self.extension_digests: dict[str, str] = {}
        for ext in extensions:
            ext_id = str(ext["extensionId"])
            self.extension_digests[ext_id] = str(ext["_digest"])
            for name, raw in ext.get("entities", {}).items():
                if name in self.entities:
                    raise MetamodelError(
                        "extension " + ext_id + " redefines entity " + name
                        + "; extensions add to the kernel, they do not replace it"
                    )
                self.entities[name] = EntitySpec(name, raw, ext_id)
            for name, raw in ext.get("vocabularies", {}).items():
                if name in self.vocabularies:
                    raise MetamodelError("extension " + ext_id + " redefines vocabulary " + name)
                self.vocabularies[name] = raw

        self.relations: dict[str, RelationSpec] = {
            name: RelationSpec(name, raw) for name, raw in root.get("relations", {}).items()
        }

        self._validate()
        self.digest = digest_with("continuity.core.v2", self.resolved_document())

    # -- integrity ---------------------------------------------------------

    def _validate(self) -> None:
        missing = [c for c in KERNEL_CONCEPTS if c not in self.entities]
        if missing:
            raise MetamodelError("kernel concepts missing from the model: " + ", ".join(missing))
        for name, entity in self.entities.items():
            for field in entity.fields.values():
                self._check_type(name + "." + field.name, field.type)
        for name, relation in self.relations.items():
            for role, target in (("domain", relation.domain), ("range", relation.range)):
                if target in (None, "*"):
                    continue
                if target not in self.entities:
                    raise MetamodelError(
                        "relation " + name + " " + role + " references unknown entity " + str(target)
                    )
            if relation.transitive and not relation.derived_from_direct:
                raise MetamodelError(
                    "transitive relation " + name + " must name its direct relation"
                )
            if relation.derived_from_direct and relation.derived_from_direct not in self.relations:
                raise MetamodelError(
                    "relation " + name + " derives from unknown direct relation "
                    + str(relation.derived_from_direct)
                )
        allowed = set(self.inference.get("allowedClosures", ()))
        transitive = {n for n, r in self.relations.items() if r.transitive}
        if transitive != allowed:
            raise MetamodelError(
                "transitive relations " + str(sorted(transitive))
                + " disagree with declared allowed closures " + str(sorted(allowed))
            )

    def _check_type(self, where: str, spec: Any) -> None:
        if isinstance(spec, str):
            if spec not in _SCALARS:
                raise MetamodelError(where + " uses unknown scalar type " + repr(spec))
            return
        if not isinstance(spec, Mapping) or len(spec) != 1:
            raise MetamodelError(where + " has a malformed type constructor")
        (ctor, arg), = spec.items()
        if ctor == "enum":
            if arg not in self.vocabularies:
                raise MetamodelError(where + " references unknown vocabulary " + repr(arg))
        elif ctor == "ref":
            if arg not in self.entities:
                raise MetamodelError(where + " references unknown entity " + repr(arg))
        elif ctor in ("list", "map"):
            self._check_type(where + "[]", arg)
        elif ctor == "object":
            if not isinstance(arg, Mapping):
                raise MetamodelError(where + " object constructor requires a field mapping")
            for sub_name, sub_raw in arg.items():
                self._check_type(where + "." + sub_name, sub_raw["type"])
        else:
            raise MetamodelError(where + " uses unknown type constructor " + repr(ctor))

    # -- projections -------------------------------------------------------

    def resolved_document(self) -> dict[str, Any]:
        """The full resolved model. This is what the semantic digest covers."""
        return {
            "metamodelVersion": self.version,
            "product": self.product,
            "productVersion": self.product_version,
            "namespace": self.namespace,
            "prefix": self.prefix,
            "extensionDigests": dict(sorted(self.extension_digests.items())),
            "vocabularies": {k: self.vocabularies[k] for k in sorted(self.vocabularies)},
            "recordEnvelope": self.record_envelope,
            "entities": {k: self.entities[k].as_dict() for k in sorted(self.entities)},
            "relations": {k: self.relations[k].as_dict() for k in sorted(self.relations)},
            "inference": self.inference,
            "runtimePolicy": self.runtime_policy,
        }

    def kernel_entities(self) -> tuple[str, ...]:
        return tuple(n for n, e in sorted(self.entities.items()) if e.kind == "KERNEL")

    def identity_entities(self) -> tuple[str, ...]:
        return tuple(n for n, e in sorted(self.entities.items()) if e.identity_bearing)

    def vocabulary_values(self, name: str) -> tuple[str, ...]:
        vocab = self.vocabularies.get(name)
        if vocab is None:
            raise MetamodelError("unknown vocabulary " + repr(name))
        return tuple(vocab["values"])

    def closure_pairs(self) -> tuple[tuple[str, str], ...]:
        """(direct relation, closure relation) pairs, in model order."""
        return tuple(
            (r.derived_from_direct, name)
            for name, r in sorted(self.relations.items())
            if r.transitive and r.derived_from_direct
        )


def default_metamodel_path() -> Path:
    """Repository-relative default: ``<repo>/ontology/metamodel.json``."""
    env = os.environ.get("ONT20_METAMODEL")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "ontology" / "metamodel.json"
        if candidate.exists():
            return candidate
    raise MetamodelError("could not locate ontology/metamodel.json; set ONT20_METAMODEL")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MetamodelError("semantic source not found: " + str(path)) from exc
    except json.JSONDecodeError as exc:
        raise MetamodelError("semantic source is not valid JSON: " + str(path) + ": " + str(exc)) from exc


def load_metamodel(path: str | os.PathLike[str] | None = None) -> Metamodel:
    """Load the metamodel and its digest-bound extensions."""
    root_path = Path(path) if path is not None else default_metamodel_path()
    root = _read_json(root_path)
    if root.get("schema") != "continuity.ontology.metamodel/2":
        raise MetamodelError("unexpected metamodel schema: " + repr(root.get("schema")))
    extensions: list[dict[str, Any]] = []
    for entry in root.get("extensions", []):
        ext_path = root_path.parent / entry["path"]
        ext = _read_json(ext_path)
        if ext.get("extensionId") != entry["id"]:
            raise MetamodelError(
                "extension id mismatch: metamodel declares " + repr(entry["id"])
                + " but " + str(ext_path) + " declares " + repr(ext.get("extensionId"))
            )
        if ext.get("requiresMetamodelVersion") != root.get("metamodelVersion"):
            raise MetamodelError(
                "extension " + entry["id"] + " requires metamodel "
                + str(ext.get("requiresMetamodelVersion"))
                + " but this is " + str(root.get("metamodelVersion"))
            )
        ext["_digest"] = digest_with("raw.file.sha256", ext_path.read_bytes())
        extensions.append(ext)
    return Metamodel(root, extensions, root_path)
