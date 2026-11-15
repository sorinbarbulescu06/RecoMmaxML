import json
import re
from pathlib import Path
from typing import Any, Optional, TextIO

from src.query.query import Condition, Field, Operator, Query, OBJECTIVE_FIELDS
from src.process.normalizer import AddressNormalizer


class HardFilterProcessor:
    """
    Etapa 2A: Trierea Exclusiva (Hard Filtering).
    Ia doar conditiile ACTIVE din OBJECTIVE_FIELDS (ignorand automat phantom_conditions)
    si verifica fiecare firma cu regula 100% Benefit of the Doubt pentru valori null/None.
    """

    def __init__(self, query: Query, temp_file_path: str | Path):
        self.query = query
        self.temp_file_path = Path(temp_file_path)
        self.temp_file_path.parent.mkdir(parents=True, exist_ok=True)

        self.hard_conditions: list[Condition] = [
            cond for cond in self.query.active_conditions
            if cond.field in OBJECTIVE_FIELDS
        ]

        self._allowed_iso_codes: set[str] = set()
        self._address_patterns: list[re.Pattern] = []
        self._compile_address_filters()

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

    def process_company(self, company: dict[str, Any], raw_json_line: Optional[str] = None) -> bool:
        self.total_seen += 1

        # A query we did not understand at all has no conditions to check.
        # Letting every company pass would look like a result, so nothing passes.
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

        # 1. Verificam intai daca se potriveste un oras/regiune/tara explicita in textul adresei (ex: 'Bucharest')
        if flat_text:
            for pattern in self._address_patterns:
                if pattern.search(flat_text):
                    return True

        # 2. Daca nu am cautat un oras specific (sau orasul e None), verificam codul ISO al tarii (ex: 'ro' in {'ro'})
        if country_code and country_code in self._allowed_iso_codes:
            # Atentie: daca query-ul a cerut strict orase (ex: "Bucharest and Cluj") si firma are town != None care NU a dat match mai sus,
            # totusi in _GEO_EXPANSIONS noi adaugam si tara 'Romania', deci country_code == 'ro' este valid.
            return True

        return False