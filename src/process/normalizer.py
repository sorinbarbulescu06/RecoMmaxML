import ast
import re
import unicodedata
from typing import Any, Optional


class AddressNormalizer:
    """
    Aplatizeaza, curata de diacritice si normalizeaza orice format de adresa
    (dict JSON, string cu dict Python, string simplu) si mapeaza tarile la ISO country_code.
    """

    _IGNORED_KEYS: set[str] = {
        "country_code", "country_name", "county", "house_number",
        "latitude", "longitude", "postcode", "raw_text",
        "region_code", "region_name", "street", "suburb", "town",
    }

    # Mapare Nume Tara (lowercase) -> Coduri ISO de 2 litere
    _COUNTRY_TO_ISO: dict[str, list[str]] = {
        "romania": ["ro"],
        "united states": ["us", "usa"],
        "usa": ["us"],
        "us": ["us"],
        "united kingdom": ["gb", "uk"],
        "uk": ["gb", "uk"],
        "england": ["gb", "uk"],
        "scotland": ["gb", "uk"],
        "wales": ["gb", "uk"],
        "northern ireland": ["gb", "uk"],
        "germany": ["de"],
        "austria": ["at"],
        "switzerland": ["ch"],
        "france": ["fr"],
        "spain": ["es"],
        "portugal": ["pt"],
        "italy": ["it"],
        "netherlands": ["nl"],
        "belgium": ["be"],
        "luxembourg": ["lu"],
        "poland": ["pl"],
        "czech republic": ["cz"],
        "czechia": ["cz"],
        "hungary": ["hu"],
        "bulgaria": ["bg"],
        "slovakia": ["sk"],
        "slovenia": ["si"],
        "croatia": ["hr"],
        "serbia": ["rs"],
        "bosnia and herzegovina": ["ba"],
        "montenegro": ["me"],
        "north macedonia": ["mk"],
        "greece": ["gr"],
        "cyprus": ["cy"],
        "malta": ["mt"],
        "albania": ["al"],
        "moldova": ["md"],
        "ukraine": ["ua"],
        "belarus": ["by"],
        "estonia": ["ee"],
        "latvia": ["lv"],
        "lithuania": ["lt"],
        "sweden": ["se"],
        "norway": ["no"],
        "denmark": ["dk"],
        "finland": ["fi"],
        "iceland": ["is"],
        "ireland": ["ie"],
        "andorra": ["ad"],
        "monaco": ["mc"],
        "liechtenstein": ["li"],
        "san marino": ["sm"],
        "vatican city": ["va"],
        "russia": ["ru"],
        "turkey": ["tr"],
        "israel": ["il"],
        "united arab emirates": ["ae", "uae"],
        "uae": ["ae", "uae"],
        "saudi arabia": ["sa"],
        "qatar": ["qa"],
        "kuwait": ["kw"],
        "bahrain": ["bh"],
        "oman": ["om"],
        "egypt": ["eg"],
        "morocco": ["ma"],
        "south africa": ["za"],
        "nigeria": ["ng"],
        "kenya": ["ke"],
        "ghana": ["gh"],
        "india": ["in"],
        "china": ["cn"],
        "japan": ["jp"],
        "south korea": ["kr"],
        "korea": ["kr"],
        "taiwan": ["tw"],
        "singapore": ["sg"],
        "hong kong": ["hk"],
        "vietnam": ["vn"],
        "thailand": ["th"],
        "indonesia": ["id"],
        "malaysia": ["my"],
        "philippines": ["ph"],
        "australia": ["au"],
        "new zealand": ["nz"],
        "canada": ["ca"],
        "brazil": ["br"],
        "mexico": ["mx"],
        "argentina": ["ar"],
        "chile": ["cl"],
        "colombia": ["co"],
        "peru": ["pe"],
    }

    @staticmethod
    def strip_accents(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text)
        return "".join(c for c in normalized if not unicodedata.combining(c))

    @classmethod
    def _parse_raw_address(cls, raw_address: Any) -> Any:
        if raw_address is None:
            return None
        if isinstance(raw_address, str):
            stripped = raw_address.strip()
            if not stripped:
                return None
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    return ast.literal_eval(stripped)
                except (ValueError, SyntaxError):
                    return stripped
            return stripped
        return raw_address

    @classmethod
    def extract_country_code_and_text(cls, raw_address: Any) -> tuple[Optional[str], str]:
        """
        Returneaza (country_code_iso, text_aplatizat_fara_country_code).
        Astfel, daca firma are 'country_code': 'kr', verificam codul ISO separat de numele oraselor!
        """
        parsed_obj = cls._parse_raw_address(raw_address)
        if parsed_obj is None:
            return None, ""

        country_code: Optional[str] = None
        tokens: list[str] = []

        if isinstance(parsed_obj, dict):
            cc_val = parsed_obj.get("country_code")
            if cc_val is not None and str(cc_val).strip().lower() != "none":
                country_code = cls.strip_accents(str(cc_val)).lower().strip()

            for k, v in parsed_obj.items():
                if v is None or k in {
                    "latitude", "longitude", "country_code",
                    "street", "house_number", "postcode", "raw_text"
                }:
                    continue
                val_str = str(v).strip()
                if val_str and val_str.lower() != "none":
                    tokens.append(val_str)
        elif isinstance(parsed_obj, list):
            for item in parsed_obj:
                if item is not None:
                    tokens.append(str(item))
        else:
            raw_str = str(parsed_obj)
            for key in cls._IGNORED_KEYS:
                raw_str = re.sub(rf"\b{key}\b", " ", raw_str, flags=re.IGNORECASE)
            raw_str = re.sub(r"\bnone\b", " ", raw_str, flags=re.IGNORECASE)
            tokens.append(raw_str)

        if not tokens:
            return country_code, ""

        combined = " ".join(tokens)
        clean_text = cls.strip_accents(combined).lower()
        clean_text = re.sub(r"[^a-z0-9\s]", " ", clean_text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        return country_code, clean_text

    @classmethod
    def flatten_address(cls, raw_address: Any) -> str:
        cc, text = cls.extract_country_code_and_text(raw_address)
        if cc and text:
            return f"{cc} {text}"
        return cc or text

    @classmethod
    def split_query_locations(cls, locations: list[str]) -> tuple[set[str], list[str]]:
        """
        Imparte locatiile din Query in:
        1. Set de coduri ISO de tara permise (ex: {'ro', 'de', 'fr', 'it'})
        2. Lista de nume de tari/orase/regiuni de cautat in textul adresei (fara coduri scurte de 2 litere care pot da false positives in strada/oras).
        """
        iso_codes: set[str] = set()
        text_locations: list[str] = []

        for loc in locations:
            clean_loc = cls.strip_accents(str(loc)).lower().strip()
            clean_loc = re.sub(r"[^a-z0-9\s]", " ", clean_loc)
            clean_loc = re.sub(r"\s+", " ", clean_loc).strip()
            if not clean_loc:
                continue

            if clean_loc in cls._COUNTRY_TO_ISO:
                for code in cls._COUNTRY_TO_ISO[clean_loc]:
                    iso_codes.add(code)

            if len(clean_loc) == 2:
                iso_codes.add(clean_loc)
            elif clean_loc not in text_locations:
                text_locations.append(clean_loc)

        return iso_codes, text_locations