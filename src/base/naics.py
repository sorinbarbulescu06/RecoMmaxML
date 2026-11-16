import json
from functools import lru_cache
from pathlib import Path

_NAICS_FILE = Path(__file__).with_name("naics.json")


@lru_cache(maxsize=1)
def load_naics() -> dict:
    """Citește o singură dată dicționarul NAICS din naics.json."""
    with open(_NAICS_FILE, encoding="utf-8") as f:
        return json.load(f)["naics_map"]


def get_naics_for_text(text: str) -> list[str]:
    """
    Căutare locală (grep) bazată pe cuvintele găsite în textul query-ului
    pentru a returna o listă unică de prefixe NAICS indulgente.
    """
    naics_map = load_naics()
    matched_prefixes: list[str] = []
    
    clean_text = text.lower()
    for keyword, prefixes in naics_map.items():
        # Căutăm cuvântul cheie ca unitate lexicală în text
        if keyword in clean_text:
            for p in prefixes:
                if p not in matched_prefixes:
                    matched_prefixes.append(p)
                    
    return matched_prefixes