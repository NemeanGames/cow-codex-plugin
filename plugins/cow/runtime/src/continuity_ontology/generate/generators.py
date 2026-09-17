"""Generate every supported representation from the one semantic source.

Nothing here is authored twice. JSON-LD, JSON Schema, SHACL/Turtle, Python
bindings and TypeScript bindings are all projections of the resolved
metamodel, and each carries a header naming the source digest so a hand edit
is detectable.

Where a representation cannot express a constraint the model declares, the
limitation is recorded in the generated manifest under ``limitations`` rather
than quietly dropped. A decorative SHACL file is not equivalent validation and
is not claimed to be.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from ..canonical.profiles import digest_with
from ..model.metamodel import Metamodel
from ..validate.validator import ID_PATTERN

__all__ = [
    "GENERATED_HEADER",
    "generate_jsonld_vocabulary",
    "generate_jsonld_context",
    "generate_json_schemas",
    "generate_shacl",
    "generate_python_bindings",
    "generate_typescript_bindings",
    "generate_all",
]

GENERATED_HEADER = "GENERATED FROM ontology/metamodel.json -- DO NOT EDIT"

_SCALAR_JSON_SCHEMA: dict[str, dict[str, Any]] = {
    "string": {"type": "string"},
    "text": {"type": "string"},
    "integer": {"type": "integer"},
    "decimal": {
        "oneOf": [
            {"type": "string", "pattern": r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$"},
            {"type": "integer"},
        ],
        "description": "Exact decimal text. Binary floats are rejected: they have no stable digest representation.",
    },
    "boolean": {"type": "boolean"},
    "timestamp": {
        "type": "string",
        "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?(Z|[+-]\d{2}:\d{2})$",
    },
    "duration_ms": {"type": "integer", "minimum": 0},
    "digest": {"type": "string", "pattern": r"^(sha256:[0-9a-f]{64}|[0-9a-f]{64})$"},
    "id": {"type": "string", "pattern": ID_PATTERN},
    "uri": {"type": "string", "pattern": r"^[a-zA-Z][a-zA-Z0-9+.-]*:"},
    "json": {},
}

_SCALAR_PY: dict[str, str] = {
    "string": "str",
    "text": "str",
    "integer": "int",
    "decimal": "str",
    "boolean": "bool",
    "timestamp": "str",
    "duration_ms": "int",
    "digest": "str",
    "id": "str",
    "uri": "str",
    "json": "Any",
}

_SCALAR_TS: dict[str, str] = {
    "string": "string",
    "text": "string",
    "integer": "number",
    "decimal": "string",
    "boolean": "boolean",
    "timestamp": "string",
    "duration_ms": "number",
    "digest": "string",
    "id": "string",
    "uri": "string",
    "json": "unknown",
}

_SCALAR_XSD: dict[str, str] = {
    "string": "xsd:string",
    "text": "xsd:string",
    "integer": "xsd:integer",
    "decimal": "xsd:decimal",
    "boolean": "xsd:boolean",
    "timestamp": "xsd:dateTime",
    "duration_ms": "xsd:integer",
    "digest": "xsd:string",
    "id": "xsd:string",
    "uri": "xsd:anyURI",
    "json": "xsd:string",
}


def _is_ref(spec: Any) -> bool:
    return isinstance(spec, Mapping) and "ref" in spec


def _ref_target(spec: Any) -> str | None:
    """The entity a type ultimately points at, looking through list and map."""
    if isinstance(spec, Mapping) and len(spec) == 1:
        (ctor, arg), = spec.items()
        if ctor == "ref":
            return str(arg)
        if ctor in ("list", "map"):
            return _ref_target(arg)
    return None


# ---------------------------------------------------------------------------
# JSON-LD
# ---------------------------------------------------------------------------

def generate_jsonld_context(model: Metamodel) -> dict[str, Any]:
    """A locally pinned context. No remote resolution occurs at runtime."""
    ctx: dict[str, Any] = {
        model.prefix: model.namespace,
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "@version": 1.1,
    }
    for name, entity in sorted(model.entities.items()):
        ctx[name] = {"@id": model.prefix + ":" + name, "@type": "@id"}
        for field_name, field in sorted(entity.fields.items()):
            term = name + "." + field_name
            ctx[term] = {"@id": model.prefix + ":" + term}
            if _is_ref(field.type):
                ctx[term]["@type"] = "@id"
    for rel_name in sorted(model.relations):
        ctx[rel_name] = {"@id": model.prefix + ":" + rel_name, "@type": "@id"}
    return {
        "_generated": GENERATED_HEADER,
        "_semanticModelDigest": model.digest,
        "@context": ctx,
    }


def generate_jsonld_vocabulary(model: Metamodel) -> dict[str, Any]:
    graph: list[dict[str, Any]] = []
    for vocab_name, vocab in sorted(model.vocabularies.items()):
        for value in vocab["values"]:
            graph.append(
                {
                    "@id": model.prefix + ":" + vocab_name + "/" + value,
                    "@type": model.prefix + ":" + vocab_name,
                    "rdfs:label": value,
                }
            )
    for name, entity in sorted(model.entities.items()):
        node: dict[str, Any] = {
            "@id": model.prefix + ":" + name,
            "@type": "rdfs:Class",
            "rdfs:label": name,
            model.prefix + ":kind": entity.kind,
        }
        if entity.doc:
            node["rdfs:comment"] = entity.doc
        graph.append(node)
        for field_name, field in sorted(entity.fields.items()):
            prop: dict[str, Any] = {
                "@id": model.prefix + ":" + name + "." + field_name,
                "@type": "rdf:Property",
                "rdfs:domain": model.prefix + ":" + name,
                "rdfs:label": field_name,
                model.prefix + ":required": field.required,
            }
            target = _ref_target(field.type)
            if target:
                prop["rdfs:range"] = model.prefix + ":" + target
            graph.append(prop)
    for rel_name, rel in sorted(model.relations.items()):
        node = {
            "@id": model.prefix + ":" + rel_name,
            "@type": "rdf:Property",
            "rdfs:label": rel_name,
            model.prefix + ":transitive": rel.transitive,
        }
        if rel.domain and rel.domain != "*":
            node["rdfs:domain"] = model.prefix + ":" + rel.domain
        if rel.range and rel.range != "*":
            node["rdfs:range"] = model.prefix + ":" + rel.range
        if rel.derived_from_direct:
            node[model.prefix + ":derivedFromDirect"] = model.prefix + ":" + rel.derived_from_direct
        graph.append(node)
    return {
        "_generated": GENERATED_HEADER,
        "_semanticModelDigest": model.digest,
        "@context": {
            model.prefix: model.namespace,
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        },
        "@graph": graph,
    }


# ---------------------------------------------------------------------------
# JSON Schema (closed)
# ---------------------------------------------------------------------------

def _schema_for_type(model: Metamodel, spec: Any) -> dict[str, Any]:
    if isinstance(spec, str):
        return dict(_SCALAR_JSON_SCHEMA[spec])
    (ctor, arg), = spec.items()
    if ctor == "enum":
        return {"type": "string", "enum": list(model.vocabulary_values(arg))}
    if ctor == "ref":
        return {
            "oneOf": [
                {"type": "string", "pattern": ID_PATTERN},
                {"$ref": "#/$defs/" + arg},
            ],
            "description": "identifier reference or embedded " + arg,
        }
    if ctor == "list":
        return {"type": "array", "items": _schema_for_type(model, arg)}
    if ctor == "map":
        return {"type": "object", "additionalProperties": _schema_for_type(model, arg)}
    if ctor == "object":
        props = {}
        required = []
        for name, sub in sorted(arg.items()):
            props[name] = _schema_for_type(model, sub["type"])
            if sub.get("required"):
                required.append(name)
        out: dict[str, Any] = {"type": "object", "properties": props, "additionalProperties": False}
        if required:
            out["required"] = required
        return out
    raise ValueError("unknown constructor " + repr(ctor))


def _entity_schema(model: Metamodel, name: str, with_envelope: bool) -> dict[str, Any]:
    entity = model.entities[name]
    props: dict[str, Any] = {}
    required: list[str] = []
    if with_envelope:
        for field_name, spec in sorted(model.record_envelope.get("fields", {}).items()):
            props[field_name] = _schema_for_type(model, spec["type"])
            if spec.get("required"):
                required.append(field_name)
    for field_name, field in sorted(entity.fields.items()):
        props[field_name] = _schema_for_type(model, field.type)
        if field.doc:
            props[field_name] = dict(props[field_name])
            props[field_name]["description"] = field.doc
        if field.required:
            required.append(field_name)
    props["x-extension"] = {
        "type": "object",
        "description": "Opaque versioned extension data. Never consulted for acceptance, authority or required behaviour.",
    }
    schema: dict[str, Any] = {
        "type": "object",
        "properties": props,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = sorted(required)
    if entity.doc:
        schema["description"] = entity.doc
    return schema


def generate_json_schemas(model: Metamodel) -> dict[str, dict[str, Any]]:
    """One closed schema document per entity, plus a bundled ``$defs`` index."""
    defs = {name: _entity_schema(model, name, with_envelope=False) for name in sorted(model.entities)}
    out: dict[str, dict[str, Any]] = {}
    for name in sorted(model.entities):
        entity = model.entities[name]
        doc: dict[str, Any] = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": model.namespace + "schema/" + name + ".schema.json",
            "title": name,
            "_generated": GENERATED_HEADER,
            "_semanticModelDigest": model.digest,
        }
        doc.update(_entity_schema(model, name, with_envelope=entity.identity_bearing))
        doc["$defs"] = defs
        out[name] = doc
    return out


# ---------------------------------------------------------------------------
# SHACL / Turtle
# ---------------------------------------------------------------------------

def _turtle_literal(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return '"' + escaped + '"'


def generate_shacl(model: Metamodel) -> tuple[str, list[str]]:
    """Emit the graph constraints SHACL can actually carry, plus limitations."""
    limitations: list[str] = []
    lines = [
        "# " + GENERATED_HEADER,
        "# semanticModelDigest: " + model.digest,
        "@prefix sh: <http://www.w3.org/ns/shacl#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix " + model.prefix + ": <" + model.namespace + "> .",
        "",
    ]
    for name in sorted(model.entities):
        entity = model.entities[name]
        shape = model.prefix + ":" + name + "Shape"
        lines.append(shape + " a sh:NodeShape ;")
        lines.append("    sh:targetClass " + model.prefix + ":" + name + " ;")
        lines.append("    sh:closed true ;")
        for field_name, field in sorted(entity.fields.items()):
            lines.append("    sh:property [")
            lines.append("        sh:path " + model.prefix + ":" + name + "." + field_name + " ;")
            constraint = _shacl_constraint(model, field.type, name + "." + field_name, limitations)
            for part in constraint:
                lines.append("        " + part + " ;")
            if field.required:
                lines.append("        sh:minCount 1 ;")
            lines.append("    ] ;")
        lines[-1] = lines[-1][:-2] + " ."
        lines.append("")

    for rel_name, rel in sorted(model.relations.items()):
        if rel.domain in (None, "*") or rel.range in (None, "*"):
            limitations.append(
                "relation " + rel_name + " has an open domain or range and carries no SHACL node shape"
            )
            continue
        if rel.min_cardinality or rel.max_cardinality:
            shape = model.prefix + ":" + rel_name + "RelationShape"
            lines.append(shape + " a sh:NodeShape ;")
            lines.append("    sh:targetClass " + model.prefix + ":" + rel.domain + " ;")
            lines.append("    sh:property [")
            lines.append("        sh:path " + model.prefix + ":" + rel_name + " ;")
            lines.append("        sh:class " + model.prefix + ":" + rel.range + " ;")
            if rel.min_cardinality:
                lines.append("        sh:minCount " + str(rel.min_cardinality) + " ;")
            if rel.max_cardinality:
                lines.append("        sh:maxCount " + str(rel.max_cardinality) + " ;")
            lines.append("    ] .")
            lines.append("")

    limitations.append(
        "SHACL carries shape, datatype and cardinality only. Transitive-closure bounds, "
        "entailment receipts, digest-domain rules, freshness, dedup keys and the "
        "exactly-once accounting partition are enforced by the Python validators and "
        "evaluators; this file does not reproduce them."
    )
    limitations.append(
        "No SHACL processor is a runtime dependency of this release, so the shapes are "
        "emitted and structurally checked but not executed against a triple store."
    )
    return "\n".join(lines) + "\n", sorted(set(limitations))


def _shacl_constraint(model: Metamodel, spec: Any, where: str, limitations: list[str]) -> list[str]:
    if isinstance(spec, str):
        return ["sh:datatype " + _SCALAR_XSD[spec]]
    (ctor, arg), = spec.items()
    if ctor == "enum":
        values = " ".join(_turtle_literal(v) for v in model.vocabulary_values(arg))
        return ["sh:in ( " + values + " )"]
    if ctor == "ref":
        return ["sh:or ( [ sh:datatype xsd:string ] [ sh:class " + model.prefix + ":" + arg + " ] )"]
    if ctor == "list":
        inner = _shacl_constraint(model, arg, where + "[]", limitations)
        return inner
    if ctor == "map":
        limitations.append(where + " is an open string-keyed map; SHACL cannot close it")
        return ["sh:nodeKind sh:BlankNodeOrIRI"]
    if ctor == "object":
        limitations.append(where + " is an inline object; its inner fields are checked by the JSON validators only")
        return ["sh:nodeKind sh:BlankNodeOrIRI"]
    return ["sh:nodeKind sh:BlankNodeOrIRI"]


# ---------------------------------------------------------------------------
# Python bindings
# ---------------------------------------------------------------------------

def _py_type(model: Metamodel, spec: Any) -> str:
    if isinstance(spec, str):
        return _SCALAR_PY[spec]
    (ctor, arg), = spec.items()
    if ctor == "enum":
        return arg
    if ctor == "ref":
        # A reference travels as an identifier or as an embedded record.
        return "str | dict[str, Any]"
    if ctor == "list":
        return "list[" + _py_type(model, arg) + "]"
    if ctor == "map":
        return "dict[str, " + _py_type(model, arg) + "]"
    if ctor == "object":
        return "dict[str, Any]"
    return "Any"


def generate_python_bindings(model: Metamodel) -> str:
    lines = [
        '"""' + GENERATED_HEADER,
        "",
        "semanticModelDigest: " + model.digest,
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from enum import Enum",
        "from typing import Any",
        "",
        "SEMANTIC_MODEL_DIGEST = " + repr(model.digest),
        "METAMODEL_VERSION = " + repr(model.version),
        "",
        "",
    ]
    for vocab_name in sorted(model.vocabularies):
        vocab = model.vocabularies[vocab_name]
        lines.append("class " + vocab_name + "(str, Enum):")
        doc = vocab.get("doc")
        if doc:
            lines.append("    " + repr(doc))
        for value in vocab["values"]:
            lines.append("    " + _py_enum_member(value) + " = " + repr(value))
        lines.append("")
        lines.append("")

    lines.append("#: Field tables keyed by entity, then field name.")
    lines.append("ENTITY_FIELDS: dict[str, dict[str, dict[str, Any]]] = {")
    for name in sorted(model.entities):
        entity = model.entities[name]
        lines.append("    " + repr(name) + ": {")
        for field_name, field in sorted(entity.fields.items()):
            lines.append(
                "        " + repr(field_name) + ": {"
                + "'type': " + repr(field.type) + ", "
                + "'required': " + repr(field.required) + ", "
                + "'python': " + repr(_py_type(model, field.type))
                + "},"
            )
        lines.append("    },")
    lines.append("}")
    lines.append("")
    lines.append("KERNEL_CONCEPTS: tuple[str, ...] = (")
    for name in model.kernel_entities():
        lines.append("    " + repr(name) + ",")
    lines.append(")")
    lines.append("")
    lines.append("IDENTITY_ENTITIES: tuple[str, ...] = (")
    for name in model.identity_entities():
        lines.append("    " + repr(name) + ",")
    lines.append(")")
    lines.append("")
    lines.append("ALLOWED_CLOSURES: tuple[tuple[str, str], ...] = (")
    for direct, closure in model.closure_pairs():
        lines.append("    (" + repr(direct) + ", " + repr(closure) + "),")
    lines.append(")")
    lines.append("")
    return "\n".join(lines)


def _py_enum_member(value: str) -> str:
    member = "".join(ch if ch.isalnum() else "_" for ch in value.upper())
    if member[0].isdigit():
        member = "V_" + member
    return member


# ---------------------------------------------------------------------------
# TypeScript bindings
# ---------------------------------------------------------------------------

def _ts_type(model: Metamodel, spec: Any) -> str:
    if isinstance(spec, str):
        return _SCALAR_TS[spec]
    (ctor, arg), = spec.items()
    if ctor == "enum":
        return arg
    if ctor == "ref":
        return "string | " + arg
    if ctor == "list":
        return "Array<" + _ts_type(model, arg) + ">"
    if ctor == "map":
        return "Record<string, " + _ts_type(model, arg) + ">"
    if ctor == "object":
        parts = []
        for name, sub in sorted(arg.items()):
            optional = "" if sub.get("required") else "?"
            parts.append(name + optional + ": " + _ts_type(model, sub["type"]))
        return "{ " + "; ".join(parts) + " }"
    return "unknown"


def generate_typescript_bindings(model: Metamodel) -> str:
    lines = [
        "// " + GENERATED_HEADER,
        "// semanticModelDigest: " + model.digest,
        "",
        "export const SEMANTIC_MODEL_DIGEST = " + json.dumps(model.digest) + ";",
        "export const METAMODEL_VERSION = " + json.dumps(model.version) + ";",
        "",
    ]
    for vocab_name in sorted(model.vocabularies):
        values = model.vocabulary_values(vocab_name)
        lines.append("export type " + vocab_name + " =")
        for index, value in enumerate(values):
            suffix = ";" if index == len(values) - 1 else ""
            lines.append("  | " + json.dumps(value) + suffix)
        lines.append("export const " + vocab_name + "_VALUES: readonly " + vocab_name + "[] = [")
        for value in values:
            lines.append("  " + json.dumps(value) + ",")
        lines.append("] as const;")
        lines.append("")

    envelope_fields = model.record_envelope.get("fields", {})
    lines.append("export interface RecordEnvelope {")
    for name, spec in sorted(envelope_fields.items()):
        optional = "" if spec.get("required") else "?"
        lines.append("  " + name + optional + ": " + _ts_type(model, spec["type"]) + ";")
    lines.append("}")
    lines.append("")

    for name in sorted(model.entities):
        entity = model.entities[name]
        base = " extends RecordEnvelope" if entity.identity_bearing else ""
        if entity.doc:
            lines.append("/** " + entity.doc.replace("*/", "*\\/") + " */")
        lines.append("export interface " + name + base + " {")
        for field_name, field in sorted(entity.fields.items()):
            optional = "" if field.required else "?"
            lines.append("  " + field_name + optional + ": " + _ts_type(model, field.type) + ";")
        lines.append('  "x-extension"?: Record<string, unknown>;')
        lines.append("}")
        lines.append("")

    lines.append("export const KERNEL_CONCEPTS = [")
    for name in model.kernel_entities():
        lines.append("  " + json.dumps(name) + ",")
    lines.append("] as const;")
    lines.append("")
    lines.append("export const ALLOWED_CLOSURES: ReadonlyArray<readonly [string, string]> = [")
    for direct, closure in model.closure_pairs():
        lines.append("  [" + json.dumps(direct) + ", " + json.dumps(closure) + "],")
    lines.append("] as const;")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def generate_all(model: Metamodel) -> dict[str, Any]:
    """Return every generated artifact keyed by repository-relative path."""
    shacl_text, limitations = generate_shacl(model)
    artifacts: dict[str, Any] = {
        "ontology/generated/context.jsonld": generate_jsonld_context(model),
        "ontology/generated/vocabulary.jsonld": generate_jsonld_vocabulary(model),
        "ontology/generated/shapes.shacl.ttl": shacl_text,
        "src/continuity_ontology/model/generated_types.py": generate_python_bindings(model),
        "generated/typescript/ontology.ts": generate_typescript_bindings(model),
    }
    for name, schema in generate_json_schemas(model).items():
        artifacts["schemas/generated/" + name + ".schema.json"] = schema
    artifacts["_limitations"] = limitations
    return artifacts


def artifact_bytes(value: Any) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def generation_manifest(model: Metamodel, artifacts: Mapping[str, Any]) -> dict[str, Any]:
    files = {
        path: digest_with("raw.file.sha256", artifact_bytes(value))
        for path, value in sorted(artifacts.items())
        if not path.startswith("_")
    }
    return {
        "schema": "ont20.generation-manifest/1",
        "semanticModelDigest": model.digest,
        "metamodelVersion": model.version,
        "extensionDigests": dict(sorted(model.extension_digests.items())),
        "generator": "continuity_ontology.generate.generators",
        "files": files,
        "limitations": list(artifacts.get("_limitations", [])),
    }
