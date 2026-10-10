"""Strict JSON decoding for policy, evidence and command-line inputs."""
from pathlib import Path
import json
import math


class StrictJSONError(ValueError):
    """Ambiguous keys or non-finite numbers are not valid evidence."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            # Do not echo keys: private evidence can contain account identifiers.
            raise StrictJSONError("Duplicate JSON object key")
        result[key] = value
    return result


def _constant(value):
    raise StrictJSONError("Non-finite JSON number")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise StrictJSONError("Non-finite JSON number")
    return number


def loads_json(text):
    """Decode text/bytes, rejecting duplicate keys and every non-finite number."""
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig")
    elif isinstance(text, str):
        text = text.removeprefix("\ufeff")
    return json.loads(text, object_pairs_hook=_object, parse_constant=_constant,
                      parse_float=_finite_float)


def load_json(path):
    """Read exact file bytes using the same strict decoder."""
    return loads_json(Path(path).read_bytes())
