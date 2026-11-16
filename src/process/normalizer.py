import ast
import re
import unicodedata
from typing import Any, Optional
from src.base.geo import load_geo


class AddressNormalizer:
    """
    Aplatizeaza, curata de diacritice si normalizeaza orice format de adresa
    (dict JSON, string cu dict Python, string simplu), mapeaza tarile la ISO country_code
    si ofera utilitare de normalizare pentru NAICS si Token Intersection.
    """

    _IGNORED_KEYS: set[str] = {
        "country_code", "country_name", "county", "house_number",
        "latitude", "longitude", "postcode", "raw_text",
        "region_code", "region_name", "street", "suburb", "town",
    }

    _STOPWORDS: set[str] = {
        "a", "an", "the", "and", "or", "for", "to", "in", "on", "at", "by", "with",
        "from", "of", "that", "which", "who", "is", "are", "was", "were", "be", "been",
        "company", "companies", "firm", "firms", "business", "businesses", "brand",
        "brands", "corporation", "inc", "ltd", "llc", "group", "solutions", "solution",
        "services", "service", "products", "product", "global", "international",
        "based", "located", "providing", "offering", "provider", "providers",
        "enterprise", "enterprises", "commercial", "industrial", "management",
        "development", "system", "systems", "platform", "platforms", "operations",
        "b2b", "b2c", "b2g", "dtc",
    }

    # Mapare Nume Tara (lowercase) -> Coduri ISO de 2 litere
    _COUNTRY_TO_ISO: dict[str, list[str]] = load_geo()["country_iso"]

    @staticmethod
    def strip_accents(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text)
        return "".join(c for c in normalized if not unicodedata.combining(c))

    @classmethod
    def _parse_raw_obj(cls, raw_val: Any) -> Any:
        if raw_val is None:
            return None
        if isinstance(raw_val, str):
            stripped = raw_val.strip()
            if not stripped or stripped.lower() == "none":
                return None
            if (stripped.startswith("{") and stripped.endswith("}")) or (
                stripped.startswith("[") and stripped.endswith("]")
            ):
                try:
                    return ast.literal_eval(stripped)
                except (ValueError, SyntaxError):
                    return stripped
            return stripped
        return raw_val

    @classmethod
    def extract_country_code_and_text(cls, raw_address: Any) -> tuple[Optional[str], str]:
        """
        Returneaza (country_code_iso, text_aplatizat_fara_country_code).
        Astfel, daca firma are 'country_code': 'kr', verificam codul ISO separat de numele oraselor!
        """
        parsed_obj = cls._parse_raw_obj(raw_address)
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
                    "street", "house_number", "postcode", "raw_text",
                }:
                    continue
                if isinstance(v, (int, float)):
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
        2. Lista de nume de tari/orase/regiuni de cautat in textul adresei.
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

    # =========================================================================
    # NORMALIZARE NAICS & TOKEN INTERSECTION (ETAPA 2A/3)
    # =========================================================================

    @classmethod
    def extract_naics_codes(cls, primary_naics: Any, secondary_naics: Any = None) -> list[str]:
        """
        Extrage toate codurile NAICS numerice (ca string-uri) din primary_naics si secondary_naics,
        indiferent daca sunt salvate ca dict, lista de dict-uri, string JSON sau int.
        """
        codes: list[str] = []

        def _collect(raw_item: Any) -> None:
            parsed = cls._parse_raw_obj(raw_item)
            if parsed is None:
                return
            if isinstance(parsed, dict):
                code_val = parsed.get("code") or parsed.get("naics_code")
                if code_val is not None:
                    digits = re.findall(r"\d{2,6}", str(code_val))
                    codes.extend(digits)
            elif isinstance(parsed, list):
                for sub in parsed:
                    _collect(sub)
            else:
                digits = re.findall(r"\d{2,6}", str(parsed))
                codes.extend(digits)

        _collect(primary_naics)
        _collect(secondary_naics)
        return list(dict.fromkeys(codes))

    @classmethod
    def _stem_token(cls, word: str) -> str:
        """
        Reduce flexiunile comune (manufacturings -> manufactur, pharmaceuticals -> pharmaceutical)
        pentru a preveni mismatch-urile artificiale la Token Intersection.
        """
        if len(word) <= 3:
            return word
        if word.endswith("ings") and len(word) > 6:
            return word[:-4]
        if word.endswith("ing") and len(word) > 5:
            return word[:-3]
        if word.endswith("ies") and len(word) > 5:
            return word[:-3] + "y"
        if word.endswith("es") and len(word) > 4 and not word.endswith(("ses", "xes", "zes")):
            return word[:-1]
        if word.endswith("s") and not word.endswith(("ss", "us", "is", "as")):
            return word[:-1]
        return word

    @classmethod
    def tokenize_and_normalize(cls, value: Any) -> set[str]:
        """
        Transforma orice string, lista sau dict intr-un set de tokeni normalizati
        (fara diacritice, lowercase, fara stopwords, cu stemming usor).
        """
        parsed = cls._parse_raw_obj(value)
        if parsed is None:
            return set()

        text_parts: list[str] = []
        if isinstance(parsed, dict):
            for v in parsed.values():
                if v is not None:
                    text_parts.append(str(v))
        elif isinstance(parsed, list):
            for item in parsed:
                if item is not None:
                    text_parts.append(str(item))
        else:
            text_parts.append(str(parsed))

        combined = " ".join(text_parts)
        clean = cls.strip_accents(combined).lower()
        raw_tokens = re.findall(r"\b(?:3d|ai|it|ev|hr|bi|vr|ar|pr|b2b|b2c|b2g|dtc|uav|gis|cad|cam|bpo|kyc|pos|erp|crm|seo|[a-z0-9]{3,})\b", clean)

        normalized_tokens: set[str] = set()
        for tok in raw_tokens:
            if tok in cls._STOPWORDS or tok.isdigit():
                continue
            normalized_tokens.add(cls._stem_token(tok))

        return normalized_tokens