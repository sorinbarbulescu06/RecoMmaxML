import re
from typing import Optional

from src.query.query import Condition, Field, Operator, Query
from src.base.config import Config
from src.base.geo import load_geo
from src.base.naics import get_naics_for_text

# NOU: Importam dictionarele separate
from src.base.dictionaries import (
    MULTIPLIERS, BUSINESS_MODELS, OFFERINGS_KEYWORDS, 
    TARGET_MARKETS_KEYWORDS, STOPWORDS
)


class LocalConditionExtractor:
    """
    Phase 1: Fast, zero-cost local rule/regex extractor for obvious hard facts.
    Adapts its aggressiveness based on whether Phase 2 (API) is available.
    """

    _GEO_EXPANSIONS: dict[str, list[str]] = load_geo()["expansions"]

    def __init__(self, brute_mode: Optional[bool] = None):
        self.brute_mode = brute_mode if brute_mode is not None else (not Config.has_api())

    def process(self, query: Query) -> Query:
        text = query.text
        occupied_spans: list[tuple[int, int]] = []

        self._extract_is_public(query, text, occupied_spans)
        self._extract_employee_count(query, text, occupied_spans)
        self._extract_revenue(query, text, occupied_spans)
        self._extract_year_founded(query, text, occupied_spans)
        self._extract_geography(query, text, occupied_spans)

        if self.brute_mode:
            self._extract_brute_mode_semantics(query, text, occupied_spans)

        return query

    @staticmethod
    def _is_overlapping(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
        start, end = span
        for o_start, o_end in occupied:
            if max(start, o_start) < min(end, o_end):
                return True
        return False

    @staticmethod
    def _get_unoccupied_text(text: str, occupied: list[tuple[int, int]]) -> str:
        chars = list(text)
        for start, end in occupied:
            for i in range(start, min(end, len(chars))):
                chars[i] = " "
        return "".join(chars)

    @staticmethod
    def _add_matched_condition(
        query: Query,
        occupied: list[tuple[int, int]],
        field: Field,
        operator: Operator,
        value: object,
        span: tuple[int, int],
        confidence: float = 1.0,
    ) -> None:
        if not LocalConditionExtractor._is_overlapping(span, occupied):
            occupied.append(span)
            query.add_condition(
                Condition(
                    field=field,
                    operator=operator,
                    value=value,
                    source="local",
                    confidence=confidence,
                    span=span,
                )
            )

    @staticmethod
    def _parse_operator(op_text: str | None, has_plus: bool = False) -> Operator:
        if has_plus:
            return Operator.GTE
        if not op_text:
            return Operator.EQ

        cleaned = op_text.strip().lower()
        if cleaned in {">=", "at least", "minimum", "min", "no less than", "starting from"}:
            return Operator.GTE
        if cleaned in {">", "more than", "over", "above", "greater than", "exceeding", "beyond", "after", "since", "later than", "newer than"}:
            return Operator.GT
        if cleaned in {"<=", "at most", "maximum", "max", "no more than", "up to"}:
            return Operator.LTE
        if cleaned in {"<", "less than", "fewer than", "under", "below", "before", "prior to", "earlier than", "older than"}:
            return Operator.LT
        return Operator.EQ

    def _parse_number(self, num_str: str, mult_str: str | None = None) -> int:
        clean_num = float(num_str.replace(",", "").strip())
        multiplier = 1
        if mult_str:
            multiplier = MULTIPLIERS.get(mult_str.strip().lower(), 1)
        return int(clean_num * multiplier)

    def _extract_is_public(self, query: Query, text: str, occupied: list[tuple[int, int]]) -> None:
        private_pattern = re.compile(
            r"\b(?:non[-\s]?public|not\s+public|unlisted|privately[-\s]+(?:held|owned)|private(?!\s+(?:equity|label|cloud|network|jet|banking|wealth|security)))\b",
            re.IGNORECASE,
        )
        for match in private_pattern.finditer(text):
            self._add_matched_condition(
                query, occupied, Field.IS_PUBLIC, Operator.EQ, False, match.span(), confidence=1.0
            )
            return

        public_pattern = re.compile(
            r"(?<![-\w])(?:publicly[-\s]+(?:traded|listed|open|owned)|stock[-\s]+listed|listed\s+on\s+stock\s+exchange|public(?!\s+(?:relations|sector|health|transport|service|services|opinion|domain|institutions|schools|safety|transit)))\b",
            re.IGNORECASE,
        )
        for match in public_pattern.finditer(text):
            self._add_matched_condition(
                query, occupied, Field.IS_PUBLIC, Operator.EQ, True, match.span(), confidence=1.0
            )
            return

    def _extract_employee_count(self, query: Query, text: str, occupied: list[tuple[int, int]]) -> None:
        range_pattern = re.compile(
            r"(?:\b(?:with|having)\s+)?(?:\bbetween\s+)?(?P<low>\d[\d,]*(?:\.\d+)?)\s*(?P<m1>k|thousand)?\s*(?:and|to|-)\s*(?P<high>\d[\d,]*(?:\.\d+)?)\s*(?P<m2>k|thousand)?\s+(?:employees|employee|staff|people|workers|headcount|team\s+members)\b",
            re.IGNORECASE,
        )
        for match in range_pattern.finditer(text):
            span = match.span()
            if not self._is_overlapping(span, occupied):
                low_val = self._parse_number(match.group("low"), match.group("m1"))
                high_val = self._parse_number(match.group("high"), match.group("m2"))
                occupied.append(span)
                query.add_condition(Condition(Field.EMPLOYEE_COUNT, Operator.GTE, low_val, "local", 1.0, span))
                query.add_condition(Condition(Field.EMPLOYEE_COUNT, Operator.LTE, high_val, "local", 1.0, span))
                return

        emp_pattern = re.compile(
            r"(?:\b(?:with|having)\s+)?(?:\ba\s+headcount\s+of\s+)?(?P<op>more\s+than|less\s+than|fewer\s+than|at\s+least|at\s+most|no\s+less\s+than|no\s+more\s+than|up\s+to|over|under|above|below|greater\s+than|exceeding|minimum|maximum|min|max|>=|<=|>|<|=)?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>k|thousand|m|million)?(?P<plus>\+)?\s+(?:employees|employee|staff|people|workers|team\s+members|headcount)\b",
            re.IGNORECASE,
        )
        for match in emp_pattern.finditer(text):
            op = self._parse_operator(match.group("op"), has_plus=bool(match.group("plus")))
            val = self._parse_number(match.group("num"), match.group("mult"))
            self._add_matched_condition(
                query, occupied, Field.EMPLOYEE_COUNT, op, val, match.span(), confidence=1.0
            )

    def _extract_revenue(self, query: Query, text: str, occupied: list[tuple[int, int]]) -> None:
        rev_prefix_pattern = re.compile(
            r"\b(?:with\s+)?(?:annual\s+|yearly\s+)?(?:revenue|revenues|turnover|sales|arr)\s+(?:of\s+)?(?P<op>more\s+than|less\s+than|fewer\s+than|at\s+least|at\s+most|no\s+less\s+than|no\s+more\s+than|minimum|maximum|min|max|over|under|above|below|greater\s+than|exceeding|beyond|up\s+to|>=|<=|>|<|=)?\s*(?:[$€£Çú]|usd|eur|gbp)?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>k|thousand|m|mil|million|millions|b|bil|billion|billions)?(?P<plus>\+)?\b",
            re.IGNORECASE,
        )
        for match in rev_prefix_pattern.finditer(text):
            if not match.group("num"):
                continue
            op = self._parse_operator(match.group("op"), has_plus=bool(match.group("plus")))
            val = self._parse_number(match.group("num"), match.group("mult"))
            self._add_matched_condition(
                query, occupied, Field.REVENUE, op, val, match.span(), confidence=1.0
            )

        rev_suffix_pattern = re.compile(
            r"(?:\b(?:with|making|generating|earning)\s+)?(?P<op>more\s+than|less\s+than|fewer\s+than|at\s+least|at\s+most|no\s+less\s+than|no\s+more\s+than|minimum|maximum|min|max|over|under|above|below|greater\s+than|exceeding|beyond|up\s+to|>=|<=|>|<|=)?\s*(?P<curr>[$€£Çú]|usd\s*|eur\s*|gbp\s*)?(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>k|thousand|m|mil|million|millions|b|bil|billion|billions)?(?P<plus>\+)?\s*(?:in\s+)?(?:annual\s+|yearly\s+)?(?:revenue|revenues|turnover|sales|arr)\b",
            re.IGNORECASE,
        )
        for match in rev_suffix_pattern.finditer(text):
            op = self._parse_operator(match.group("op"), has_plus=bool(match.group("plus")))
            val = self._parse_number(match.group("num"), match.group("mult"))
            self._add_matched_condition(
                query, occupied, Field.REVENUE, op, val, match.span(), confidence=1.0
            )

    def _extract_year_founded(self, query: Query, text: str, occupied: list[tuple[int, int]]) -> None:
        year_explicit_pattern = re.compile(
            r"\b(?:founded|established|started|created|launched|incorporated)?\s*(?P<op>after|since|before|prior\s+to|in|on|later\s+than|earlier\s+than|newer\s+than|older\s+than|from|>=|<=|>|<|=)\s+(?P<year>(?:19|20)\d{2})\b"
            r"|\b(?:founded|established|started|created|launched|incorporated)\s+(?P<year_direct>(?:19|20)\d{2})\b",
            re.IGNORECASE,
        )
        for match in year_explicit_pattern.finditer(text):
            year_str = match.group("year") or match.group("year_direct")
            if not year_str:
                continue
            op_str = match.group("op")
            if op_str and op_str.strip().lower() in {"since", "from"}:
                op = Operator.GTE
            else:
                op = self._parse_operator(op_str)
            self._add_matched_condition(
                query, occupied, Field.YEAR_FOUNDED, op, int(year_str), match.span(), confidence=1.0
            )

        bare_year_pattern = re.compile(r"\b(?P<year>19[5-9]\d|20[0-2]\d)\b")
        for match in bare_year_pattern.finditer(text):
            span = match.span()
            if not self._is_overlapping(span, occupied):
                self._add_matched_condition(
                    query, occupied, Field.YEAR_FOUNDED, Operator.EQ, int(match.group("year")), span, confidence=0.85
                )

    def _extract_geography(
        self, query: Query, text: str, occupied: list[tuple[int, int]]
    ) -> None:
        def add(expanded: list[str], span: tuple[int, int]) -> None:
            occupied.append(span)
            query.add_condition(
                Condition(Field.ADDRESS, Operator.IN, list(expanded), "local", 0.85, span)
            )

        for geo_key in sorted(self._GEO_EXPANSIONS.keys(), key=len, reverse=True):
            pattern = re.compile(
                rf"(?:\b(?:in|from|based\s+in|located\s+in)\s+)?(?:\bthe\s+)?\b{re.escape(geo_key)}\b",
                re.IGNORECASE,
            )
            for match in pattern.finditer(text):
                if not self._is_overlapping(match.span(), occupied):
                    add(self._GEO_EXPANSIONS[geo_key], match.span())

        for match in re.finditer(r"\bUS\b", text):
            if not self._is_overlapping(match.span(), occupied):
                add(self._GEO_EXPANSIONS["usa"], match.span())

    def _extract_brute_mode_semantics(
        self, query: Query, text: str, occupied: list[tuple[int, int]]
    ) -> None:
        local_naics = get_naics_for_text(text)
        if local_naics:
            query.add_condition(
                Condition(
                    field=Field.PRIMARY_NAICS,
                    operator=Operator.IN,
                    value=local_naics,
                    source="local",
                    confidence=0.85
                )
            )
        for_split = re.search(r"\b(?:for|serving|to|working\s+with|competing\s+with)\b", text, re.IGNORECASE)

        offerings_values: list[str] = []
        generic_keys = {"software", "hardware", "retail", "it", "tech", "automation", "electronics"}
        sorted_off_keys = sorted(
            OFFERINGS_KEYWORDS.keys(),
            key=lambda k: (k not in generic_keys, len(k)),
            reverse=True,
        )
        for off_key in sorted_off_keys:
            off_expanded = OFFERINGS_KEYWORDS[off_key]
            pattern = re.compile(rf"\b{re.escape(off_key)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                if for_split and match.start() >= for_split.start() and off_key in TARGET_MARKETS_KEYWORDS:
                    continue
                if not self._is_overlapping(match.span(), occupied):
                    occupied.append(match.span())
                    for item in off_expanded:
                        if item not in offerings_values:
                            offerings_values.append(item)

        if offerings_values:
            query.add_condition(
                Condition(Field.CORE_OFFERINGS, Operator.IN, offerings_values, "local", 0.85)
            )

        tm_values: list[str] = []
        for tm_key in sorted(TARGET_MARKETS_KEYWORDS.keys(), key=len, reverse=True):
            tm_expanded = TARGET_MARKETS_KEYWORDS[tm_key]
            pattern = re.compile(rf"\b{re.escape(tm_key)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                if not self._is_overlapping(match.span(), occupied):
                    occupied.append(match.span())
                    for item in tm_expanded:
                        if item not in tm_values:
                            tm_values.append(item)

        if tm_values:
            query.add_condition(
                Condition(Field.TARGET_MARKETS, Operator.IN, tm_values, "local", 0.85)
            )

        bm_values: list[str] = []
        bm_limit = for_split.start() if for_split else len(text)

        for bm_key in sorted(BUSINESS_MODELS.keys(), key=len, reverse=True):
            bm_expanded = BUSINESS_MODELS[bm_key]
            pattern = re.compile(rf"\b{re.escape(bm_key)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                if match.start() < bm_limit and not self._is_overlapping(match.span(), occupied):
                    occupied.append(match.span())
                    for item in bm_expanded:
                        if item not in bm_values:
                            bm_values.append(item)

        if bm_values:
            query.add_condition(
                Condition(Field.BUSINESS_MODEL, Operator.IN, bm_values, "local", 0.80)
            )

        unoccupied_text = self._get_unoccupied_text(text, occupied).lower()
        remainder_words = re.findall(r"\b(?:3d|ai|it|ev|hr|bi|vr|ar|pr|uav|gis|cad|cam|bpo|[a-z]{3,})\b", unoccupied_text)
        desc_keywords: list[str] = []
        for word in remainder_words:
            if word not in STOPWORDS and word not in desc_keywords:
                desc_keywords.append(word)

        for item in offerings_values[:3]:
            if item not in desc_keywords:
                desc_keywords.append(item)

        if desc_keywords:
            query.add_condition(
                Condition(Field.DESCRIPTION, Operator.IN, desc_keywords, "local", 0.70)
            )