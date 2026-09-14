"""Read legacy receipt digests without rewriting frozen evidence."""
import json
import re
from pathlib import Path
from ..equivalence.evaluator import refuse_guessed_savings


def normalize_receipt(receipt):
    refuse_guessed_savings(receipt, 'receipt')
    def walk(value):
        if isinstance(value, dict):
            result = {}
            for key, child in value.items():
                if key in ('extractSha256', 'transcriptSha256') and child is not None:
                    bare = child.removeprefix('sha256:')
                    if not re.fullmatch('[0-9a-f]{64}', bare):
                        raise ValueError('invalid receipt digest ' + key)
                    child = 'sha256:' + bare
                result[key] = walk(child)
            return result
        if isinstance(value, list):
            return [walk(child) for child in value]
        return value
    return walk(receipt)


def read_receipt(path):
    return normalize_receipt(json.loads(Path(path).read_text(encoding='utf-8')))


def write_receipt(path, receipt):
    Path(path).write_text(json.dumps(normalize_receipt(receipt), indent=2) + '\n', encoding='utf-8')
