import json
import re
from pathlib import Path
from typing import Any, Optional, TextIO

from src.query.query import Condition, Field, Operator, Query, OBJECTIVE_FIELDS
from src.process.normalizer import AddressNormalizer


class HardFilterProcessor:
    """
    Etapa 2A: Trierea Exclusiva (Hard Filtering).
    1. Verifica conditiile ACTIVE din OBJECTIVE_FIELDS cu regula 100% Benefit of the Doubt.
    2. Verifica criteriul hibrid de industrie:
       - Match pe prefixele NAICS (daca exista in query si in firma)
       - Fallback pe Token Intersection (core_offerings + business_model din query vs. descrierea firmei)
         raportat la un prag de toleranta flexibil (industry_threshold).
    """

    DEFAULT_INDUSTRY_THRESHOLD: float = 0.15

    def __init__(
        self,
        query: Query,
        temp_file_path: str | Path,
        industry_threshold: float = DEFAULT_INDUSTRY_THRESHOLD,
    ):
        self.query = query
        self.temp_file_path = Path(temp_file_path)
        self.temp_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.industry_threshold = industry_threshold

        self.hard_conditions: list[Condition] = [
            cond for cond in self.query.active_conditions
            if cond.field in OBJECTIVE_FIELDS
        ]

        self._allowed_iso_codes: set[str] = set()
        self._address_patterns: list[re.Pattern] = []
        self._compile_address_filters()

        self._query_naics_prefixes: tuple[str, ...] = ()
        self._query_industry_tokens: set[str] = set()
        self._has_industry_filter: bool = False
        self._compile_industry_filters()

        self.total_seen: int = 0
        self.total_passed: int = 0
        self.total_dropped: int = 0

        self._file_handle: Optional[TextIO] = None

    def __enter__(self) -> "HardFilterProcessor":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def open(self) -> None:
        if self._file_handle is None:
            self._file_handle = open(self.temp_file_path, mode="w", encoding="utf-8")

    def close(self) -> None:
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None

    def _compile_address_filters(self) -> None:
        all_locs: list[str] = []
        for cond in self.hard_conditions:
            if cond.field == Field.ADDRESS and not cond.is_phantom:
                raw_locs = cond.value if isinstance(cond.value, list) else [str(cond.value)]
                all_locs.extend(raw_locs)

        if all_locs:
            iso_codes, text_locs = AddressNormalizer.split_query_locations(all_locs)
            self._allowed_iso_codes = iso_codes
            self._address_patterns = [
                re.compile(rf"\b{re.escape(loc)}\b", re.IGNORECASE)
                for loc in text_locs
            ]

    def _compile_industry_filters(self) -> None:
        """
        Precalculeaza din Query:
        1. Prefixele NAICS permise (ex: ('3254', '5417'))
        2. Setul de tokeni specifici din CORE_OFFERINGS pentru Token Intersection
           (fara business_model, ca 'B2B'/'Service Provider' sa nu califice firme din alte domenii).
        """
        naics_prefixes: list[str] = []
        industry_tokens: set[str] = set()

        for cond in self.query.active_conditions:
            if cond.field in (Field.PRIMARY_NAICS, Field.SECONDARY_NAICS):
                vals = cond.value if isinstance(cond.value, list) else [cond.value]
                for v in vals:
                    digits = re.findall(r"\d{2,6}", str(v))
                    for d in digits:
                        if d not in naics_prefixes:
                            naics_prefixes.append(d)
            elif cond.field == Field.CORE_OFFERINGS:
                industry_tokens.update(AddressNormalizer.tokenize_and_normalize(cond.value))

        self._query_naics_prefixes = tuple(naics_prefixes)
        self._query_industry_tokens = industry_tokens
        self._has_industry_filter = bool(self._query_naics_prefixes or self._query_industry_tokens)

    def process_company(self, company: dict[str, Any], raw_json_line: Optional[str] = None) -> bool:
        self.total_seen += 1

        if self.query.status == "failed":
            self.total_dropped += 1
            return False

        if self._passes_all_hard_filters(company):
            self.total_passed += 1
            if self._file_handle is not None:
                if raw_json_line is not None:
                    line = raw_json_line.rstrip("\r\n") + "\n"
                else:
                    line = json.dumps(company, ensure_ascii=False) + "\n"
                self._file_handle.write(line)
            return True

        self.total_dropped += 1
        return False

    def _passes_all_hard_filters(self, company: dict[str, Any]) -> bool:
        # 1. Filtrele obiective clasice (is_public, year_founded, employee_count, revenue, address)
        for cond in self.hard_conditions:
            if cond.field == Field.IS_PUBLIC:
                if not self._check_boolean(company.get("is_public"), cond):
                    return False
            elif cond.field in (Field.YEAR_FOUNDED, Field.EMPLOYEE_COUNT, Field.REVENUE):
                if not self._check_numeric(company.get(cond.field.value), cond):
                    return False
            elif cond.field == Field.ADDRESS:
                if not self._check_address(company.get("address")):
                    return False

        # 2. Filtrul hibrid de industrie (NAICS match -> Fallback Token Intersection pe descriere)
        if self._has_industry_filter:
            if not self._check_industry_or_description(company):
                return False

        return True

    @staticmethod
    def _check_boolean(company_val: Any, cond: Condition) -> bool:
        if company_val is None:
            return True

        if isinstance(company_val, bool):
            actual_bool = company_val
        elif isinstance(company_val, str):
            low = company_val.strip().lower()
            if low in {"true", "1", "yes"}:
                actual_bool = True
            elif low in {"false", "0", "no"}:
                actual_bool = False
            else:
                return True
        else:
            return True

        expected_bool = bool(cond.value) if not isinstance(cond.value, str) else (cond.value.strip().lower() == "true")
        if cond.operator == Operator.EQ:
            return actual_bool == expected_bool
        return True

    @staticmethod
    def _check_numeric(company_val: Any, cond: Condition) -> bool:
        if company_val is None:
            return True

        try:
            actual_num = float(company_val)
            target_num = float(cond.value)
        except (ValueError, TypeError):
            return True

        op = cond.operator
        if op == Operator.EQ:
            return actual_num == target_num
        if op == Operator.GT:
            return actual_num > target_num
        if op == Operator.GTE:
            return actual_num >= target_num
        if op == Operator.LT:
            return actual_num < target_num
        if op == Operator.LTE:
            return actual_num <= target_num
        return True

    def _check_address(self, raw_address: Any) -> bool:
        if not self._allowed_iso_codes and not self._address_patterns:
            return True

        country_code, flat_text = AddressNormalizer.extract_country_code_and_text(raw_address)

        # 100% Benefit of the Doubt daca firma nu are nici country_code, nici text de adresa
        if not country_code and not flat_text:
            return True

        # 1. Daca firma are country_code si query-ul specifica tari (ISO codes),
        # decizia se ia strict pe baza codului de tara (nicio strada/oras omonim din alta tara nu poate trece).
        if country_code and self._allowed_iso_codes:
            return country_code in self._allowed_iso_codes

        # 2. Fallback: daca firma NU are country_code (sau query-ul contine doar un oras necunoscut),
        # cautam in textul curatat (oras / regiune).
        if flat_text:
            for pattern in self._address_patterns:
                if pattern.search(flat_text):
                    return True

        return False

    def _check_industry_or_description(self, company: dict[str, Any]) -> bool:
        """
        Pasul A: Verifica daca vreun cod NAICS al firmei incepe cu vreun prefix NAICS din query.
        Pasul B (Fallback): Daca NAICS-ul lipseste sau nu da match, calculeaza Token Intersection
        intre CORE_OFFERINGS din query si (core_offerings + description + naics label) ale firmei.
        """
        company_naics = AddressNormalizer.extract_naics_codes(
            company.get("primary_naics"),
            company.get("secondary_naics"),
        )

        # Pasul A: Match pe NAICS
        if self._query_naics_prefixes and company_naics:
            for c_code in company_naics:
                for q_prefix in self._query_naics_prefixes:
                    if c_code.startswith(q_prefix) or q_prefix.startswith(c_code):
                        return True

        if not self._query_industry_tokens:
            return not bool(company_naics)

        # Pasul B: Fallback pe Token Intersection (fara business_model!)
        company_text_fields = [
            company.get("core_offerings"),
            company.get("description"),
            company.get("primary_naics"),
            company.get("secondary_naics"),
        ]
        company_tokens = AddressNormalizer.tokenize_and_normalize(company_text_fields)

        # Corner case: Firma complet goala -> Benefit of the Doubt
        if not company_naics and not company_tokens:
            return True

        if not company_tokens:
            return False

        intersection = self._query_industry_tokens.intersection(company_tokens)
        if not intersection:
            return False

        overlap_score = len(intersection) / len(self._query_industry_tokens)
        return overlap_score >= self.industry_threshold