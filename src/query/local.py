import re
from typing import Optional

from src.query.query import Condition, Field, Operator, Query
from src.base.config import Config


class LocalConditionExtractor:
    """
    Phase 1: Fast, zero-cost local rule/regex extractor for obvious hard facts.
    Adapts its aggressiveness based on whether Phase 2 (API) is available.
    """

    # Multiplicatori numerici pentru revenue / employees (ex: 50M, 10k)
    _MULTIPLIERS: dict[str, int] = {
        "k": 1_000,
        "thousand": 1_000,
        "m": 1_000_000,
        "mil": 1_000_000,
        "million": 1_000_000,
        "millions": 1_000_000,
        "b": 1_000_000_000,
        "bil": 1_000_000_000,
        "billion": 1_000_000_000,
        "billions": 1_000_000_000,
    }

    # --- DICTIONARE PENTRU BRUTE-MODE (cand API-ul este inactiv) ---
    _GEO_EXPANSIONS: dict[str, list[str]] = {
        "scandinavia": ["Sweden", "Norway", "Denmark", "Finland", "Iceland"],
        "nordic": ["Sweden", "Norway", "Denmark", "Finland", "Iceland"],
        "balkans": ["Romania", "Bulgaria", "Greece", "Serbia", "Croatia", "Slovenia", "Albania"],
        "eastern europe": ["Romania", "Poland", "Czechia", "Hungary", "Bulgaria", "Slovakia", "Ukraine"],
        "western europe": ["Germany", "France", "United Kingdom", "UK", "Netherlands", "Belgium", "Switzerland"],
        "europe": ["Germany", "France", "United Kingdom", "Romania", "Poland", "Spain", "Italy", "Netherlands", "Sweden"],
        "romania": ["Romania", "Bucharest", "Cluj", "Timisoara", "Iasi", "Brasov"],
        "usa": ["United States", "USA", "US", "New York", "California", "Texas"],
        "united states": ["United States", "USA", "US"],
        "uk": ["United Kingdom", "UK", "London", "England"],
        "germany": ["Germany", "Berlin", "Munich"],
        "france": ["France", "Paris"],
        "french": ["France", "Paris"],
        "german": ["Germany", "Berlin", "Munich"],
        "romanian": ["Romania", "Bucharest", "Brasov", "Cluj"],
    }

    _BUSINESS_MODELS: dict[str, list[str]] = {
        "b2b": ["B2B", "business-to-business", "enterprise"],
        "b2c": ["B2C", "direct-to-consumer", "DTC", "consumer"],
        "direct-to-consumer": ["direct-to-consumer", "DTC", "B2C", "consumer"],
        "dtc": ["direct-to-consumer", "DTC", "B2C"],
        "saas": ["SaaS", "software as a service", "cloud", "subscription"],
        "supply": ["supplier", "manufacturer", "distributor", "B2B", "wholesale"],
        "supplier": ["supplier", "manufacturer", "distributor", "B2B"],
        "manufacturer": ["manufacturer", "manufacturing", "production", "supplier"],
        "manufacturing": ["manufacturer", "manufacturing", "production"],
        "agency": ["agency", "consulting", "services"],
        "marketplace": ["marketplace", "platform"],
    }

    _OFFERINGS_KEYWORDS: dict[str, list[str]] = {
        "software": ["software", "SaaS", "platform", "application", "cloud", "IT"],
        "packaging": ["packaging", "packaging materials", "containers", "bottles", "jars", "boxes", "tubes"],
        "logistics": ["logistics", "supply chain", "freight", "shipping", "warehousing", "transportation"],
        "fintech": ["fintech", "financial technology", "payments", "banking", "finance"],
        "ai": ["artificial intelligence", "AI", "machine learning", "ML", "data science"],
        "cybersecurity": ["cybersecurity", "security", "infosec", "network security"],
        "biotech": ["biotechnology", "biotech", "life sciences", "pharma", "pharmaceuticals"],
        "ecommerce": ["e-commerce", "ecommerce", "online retail", "retail"],
        "hardware": ["hardware", "electronics", "semiconductors", "devices"],
    }

    _TARGET_MARKETS_KEYWORDS: dict[str, list[str]] = {
        "cosmetics": ["cosmetics", "beauty", "personal care", "skincare"],
        "beauty": ["beauty", "cosmetics", "personal care", "skincare"],
        "healthcare": ["healthcare", "medical", "hospitals", "clinics", "health"],
        "automotive": ["automotive", "cars", "vehicles", "mobility"],
        "retail": ["retail", "e-commerce", "consumer goods", "brands"],
        "finance": ["finance", "banking", "financial services", "insurance"],
        "enterprise": ["enterprise", "corporate", "B2B"],
    }

    _STOPWORDS: set[str] = {
        "a", "an", "the", "and", "or", "for", "to", "in", "on", "at", "by", "with",
        "from", "of", "that", "which", "who", "could", "would", "should", "can",
        "company", "companies", "firm", "firms", "business", "businesses", "brand",
        "brands", "looking", "find", "search", "more", "than", "less", "over", "under",
    }

    def __init__(self, brute_mode: Optional[bool] = None):
        # Daca nu este pasat explicit, activam Brute-Mode automat cand nu exista API Key
        self.brute_mode = brute_mode if brute_mode is not None else (not Config.has_api())

    def process(self, query: Query) -> Query:
        """
        Extracts deterministic conditions from the query text and populates spans.
        Anything not matched stays in `query.remainder` for Phase 2 (API).
        """
        text = query.text
        occupied_spans: list[tuple[int, int]] = []

        # 1. STANDARD HARD-FACTS (Ruleaza MEREU, si cu API si fara API)
        self._extract_is_public(query, text, occupied_spans)
        self._extract_employee_count(query, text, occupied_spans)
        self._extract_revenue(query, text, occupied_spans)
        self._extract_year_founded(query, text, occupied_spans)

        # 2. BRUTE-MODE OVERDRIVE (Ruleaza DOAR cand nu avem API Key)
        if self.brute_mode:
            self._extract_brute_mode_semantics(query, text, occupied_spans)

        return query

    # =========================================================================
    # HELPERE PENTRU SPANS SI OPERATORI
    # =========================================================================

    @staticmethod
    def _is_overlapping(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
        start, end = span
        for o_start, o_end in occupied:
            if max(start, o_start) < min(end, o_end):
                return True
        return False

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
            multiplier = self._MULTIPLIERS.get(mult_str.strip().lower(), 1)
        return int(clean_num * multiplier)

    # =========================================================================
    # EXTRACTORI HARD-FACTS (STANDARD MODE)
    # =========================================================================

    def _extract_is_public(self, query: Query, text: str, occupied: list[tuple[int, int]]) -> None:
        # 1. Cautam mai intai negatiile explicite sau statutul privat (is_public == False)
        private_pattern = re.compile(
            r"\b(?:non[-\s]?public|not\s+public|unlisted|privately[-\s]+(?:held|owned)|private(?=\s+(?:company|companies|firm|firms|sector|business)))\b",
            re.IGNORECASE,
        )
        for match in private_pattern.finditer(text):
            self._add_matched_condition(
                query, occupied, Field.IS_PUBLIC, Operator.EQ, False, match.span(), confidence=1.0
            )
            return

        # 2. Cautam indicatori de companie listata la bursa (is_public == True)
        # Evitam "public relations", "public sector", "general public"
        public_pattern = re.compile(
            r"(?<![-\w])(?:publicly[-\s]+(?:traded|listed|open|owned)|stock[-\s]+listed|listed\s+on\s+stock\s+exchange|public(?!\s+(?:relations|sector|health|transport|service|services|opinion|domain)))\b",
            re.IGNORECASE,
        )
        for match in public_pattern.finditer(text):
            self._add_matched_condition(
                query, occupied, Field.IS_PUBLIC, Operator.EQ, True, match.span(), confidence=1.0
            )
            return

    def _extract_employee_count(self, query: Query, text: str, occupied: list[tuple[int, int]]) -> None:
        # Cazul A: Interval (ex: "between 100 and 500 employees" sau "100-500 employees")
        range_pattern = re.compile(
            r"(?:\b(?:with|having)\s+)?(?:\bbetween\s+)?(?P<low>\d[\d,]*(?:\.\d+)?)\s*(?P<m1>k|thousand)?\s*(?:and|to|-)\s*(?P<high>\d[\d,]*(?:\.\d+)?)\s*(?P<m2>k|thousand)?\s+(?:employees|employee|staff|people|workers|headcount)\b",
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

        # Cazul B: Comparator optional + numar + unitate (ex: "with more than 1,000 employees" sau "500+ employees" sau "500 employees")
        emp_pattern = re.compile(
            r"(?:\b(?:with|having)\s+)?(?P<op>more\s+than|less\s+than|fewer\s+than|at\s+least|at\s+most|no\s+less\s+than|no\s+more\s+than|up\s+to|over|under|above|below|greater\s+than|minimum|maximum|min|max|>=|<=|>|<|=)?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>k|thousand|m|million)?(?P<plus>\+)?\s+(?:employees|employee|staff|people|workers|team\s+members|headcount)\b",
            re.IGNORECASE,
        )
        for match in emp_pattern.finditer(text):
            op = self._parse_operator(match.group("op"), has_plus=bool(match.group("plus")))
            val = self._parse_number(match.group("num"), match.group("mult"))
            self._add_matched_condition(
                query, occupied, Field.EMPLOYEE_COUNT, op, val, match.span(), confidence=1.0
            )

    def _extract_revenue(self, query: Query, text: str, occupied: list[tuple[int, int]]) -> None:
        # Cazul A: "revenue over $50 million" / "annual sales > 10M"
        rev_prefix_pattern = re.compile(
            r"\b(?:with\s+)?(?:annual\s+|yearly\s+)?(?:revenue|revenues|turnover|sales|arr)\s+(?:of\s+)?(?P<op>more\s+than|less\s+than|at\s+least|at\s+most|over|under|above|below|greater\s+than|up\s+to|>=|<=|>|<|=)?\s*(?:[$€£]|usd|eur)?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>k|thousand|m|mil|million|millions|b|bil|billion|billions)?(?P<plus>\+)?\b",
            re.IGNORECASE,
        )
        for match in rev_prefix_pattern.finditer(text):
            op = self._parse_operator(match.group("op"), has_plus=bool(match.group("plus")))
            val = self._parse_number(match.group("num"), match.group("mult"))
            self._add_matched_condition(
                query, occupied, Field.REVENUE, op, val, match.span(), confidence=1.0
            )

        # Cazul B: "over $50M in revenue" / "$10 million revenue" / "> $5M"
        rev_suffix_pattern = re.compile(
            r"(?:\b(?:with|making|generating|earning)\s+)?(?P<op>more\s+than|less\s+than|at\s+least|at\s+most|over|under|above|below|greater\s+than|up\s+to|>=|<=|>|<|=)?\s*(?P<curr>[$€£]|usd\s*|eur\s*)?(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>k|thousand|m|mil|million|millions|b|bil|billion|billions)?(?P<plus>\+)?\s*(?:in\s+)?(?:annual\s+|yearly\s+)?(?:revenue|revenues|turnover|sales|arr)\b",
            re.IGNORECASE,
        )
        for match in rev_suffix_pattern.finditer(text):
            op = self._parse_operator(match.group("op"), has_plus=bool(match.group("plus")))
            val = self._parse_number(match.group("num"), match.group("mult"))
            self._add_matched_condition(
                query, occupied, Field.REVENUE, op, val, match.span(), confidence=1.0
            )

    def _extract_year_founded(self, query: Query, text: str, occupied: list[tuple[int, int]]) -> None:
        # Cazul A: Cu indicator explicit ("founded after 2018", "established in 2015", "since 2020")
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
            # "since 2018" -> >= 2018; "after 2018" -> > 2018
            if op_str and op_str.strip().lower() in {"since", "from"}:
                op = Operator.GTE
            else:
                op = self._parse_operator(op_str)
            self._add_matched_condition(
                query, occupied, Field.YEAR_FOUNDED, op, int(year_str), match.span(), confidence=1.0
            )

        # Cazul B: An izolat fara cuvant de legatura (ex: "software 2018 500 employees")
        # Doar daca nu a fost deja prins la angajati/revenue/anul explicit
        bare_year_pattern = re.compile(r"\b(?P<year>19[5-9]\d|20[0-2]\d)\b")
        for match in bare_year_pattern.finditer(text):
            span = match.span()
            if not self._is_overlapping(span, occupied):
                self._add_matched_condition(
                    query, occupied, Field.YEAR_FOUNDED, Operator.EQ, int(match.group("year")), span, confidence=0.85
                )

    # =========================================================================
    # BRUTE-MODE FALLBACK (CAND LIPSESTE CHEIA API)
    # =========================================================================

    def _extract_brute_mode_semantics(
        self, query: Query, text: str, occupied: list[tuple[int, int]]
    ) -> None:
        # 1. Geografie / Regiuni
        address_values: list[str] = []
        for geo_key, expanded_locations in self._GEO_EXPANSIONS.items():
            pattern = re.compile(rf"(?:\b(?:in|from|based\s+in|located\s+in)\s+)?\b{re.escape(geo_key)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                if not self._is_overlapping(match.span(), occupied):
                    occupied.append(match.span())
                    for loc in expanded_locations:
                        if loc not in address_values:
                            address_values.append(loc)

        if address_values:
            query.add_condition(
                Condition(Field.ADDRESS, Operator.IN, address_values, "local", 0.85)
            )

        # 2. Business Model (B2B, B2C, supplier, manufacturer, SaaS)
        bm_values: list[str] = []
        for bm_key, bm_expanded in self._BUSINESS_MODELS.items():
            pattern = re.compile(rf"\b{re.escape(bm_key)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                if not self._is_overlapping(match.span(), occupied):
                    occupied.append(match.span())
                    for item in bm_expanded:
                        if item not in bm_values:
                            bm_values.append(item)

        if bm_values:
            query.add_condition(
                Condition(Field.BUSINESS_MODEL, Operator.IN, bm_values, "local", 0.80)
            )

        # 3. Core Offerings (Industrii / Produse cunoscute)
        offerings_values: list[str] = []
        for off_key, off_expanded in self._OFFERINGS_KEYWORDS.items():
            pattern = re.compile(rf"\b{re.escape(off_key)}(?:\s+materials|\s+solutions|\s+services)?\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                if not self._is_overlapping(match.span(), occupied):
                    occupied.append(match.span())
                    for item in off_expanded:
                        if item not in offerings_values:
                            offerings_values.append(item)

        if offerings_values:
            query.add_condition(
                Condition(Field.CORE_OFFERINGS, Operator.IN, offerings_values, "local", 0.85)
            )

        # 4. Target Markets (Segmente de clienti)
        tm_values: list[str] = []
        for tm_key, tm_expanded in self._TARGET_MARKETS_KEYWORDS.items():
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

        # 5. Fallback pe cuvintele ramase in query.remainder pentru DESCRIPTION
        remainder_words = re.findall(r"[a-zA-Z]{3,}", query.remainder.lower())
        desc_keywords: list[str] = []
        for word in remainder_words:
            if word not in self._STOPWORDS and word not in desc_keywords:
                desc_keywords.append(word)

        # Adaugam si cuvintele principale din offerings in description pentru recall mai bun in Brute-Mode
        for item in offerings_values[:3]:
            if item not in desc_keywords:
                desc_keywords.append(item)

        if desc_keywords:
            query.add_condition(
                Condition(Field.DESCRIPTION, Operator.IN, desc_keywords, "local", 0.70)
            )