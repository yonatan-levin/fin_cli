import json
from typing import Any, Tuple


def json_to_tuples(json_string: str) -> Tuple[Any, ...]:
    """Convert a JSON string (list or dict) to a tuple.

    This is a direct port of the legacy helper previously located at
    core.converters.json.json_to_tuples. It is kept here so the new
    configuration system does not depend on the deprecated *core* package.
    """
    try:
        # SEC & other sources sometimes use single quotes; normalise to double
        json_string = json_string.replace("'", '"')
        data = json.loads(json_string)
        if isinstance(data, list):
            return tuple(data)
        if isinstance(data, dict):
            return tuple(data.items())
        # Fallback: not list/dict – return empty tuple
        return ()
    except Exception as exc:
        # Preserve original behaviour: print then re-raise
        print("Error converting from JSON:", exc)
        raise
