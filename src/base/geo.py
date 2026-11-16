import json
from functools import lru_cache
from pathlib import Path

_GEO_FILE = Path(__file__).with_name("geo.json")


@lru_cache(maxsize=1)
def load_geo() -> dict:
    """The single geography table (see geo.json). Read once, shared by every module."""
    with open(_GEO_FILE, encoding="utf-8") as f:
        return json.load(f)
