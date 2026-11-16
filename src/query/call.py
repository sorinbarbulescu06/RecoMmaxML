import re
from typing import Optional
from pydantic import BaseModel, Field as PydanticField
from google import genai
from google.genai import types

from src.query.query import Condition, Field, Operator, Query
from src.query.local import LocalConditionExtractor
from src.base.config import Config


class APIConditionItem(BaseModel):
    field: Field = PydanticField(
        description="The target company field to filter or match against."
    )
    operator: Operator = PydanticField(
        description="Use 'in' for lists of keywords/locations, '==' for exact booleans/strings, or '>', '<', '>=', '<=' for numbers."
    )
    value_string: Optional[str] = PydanticField(
        default=None,
        description="Use this if the value is a single string, number, or boolean.",
    )
    value_list: Optional[list[str]] = PydanticField(
        default=None,
        description="Use this when operator is 'in' to provide multiple expanded keywords, synonyms, or countries.",
    )
    confidence: float = PydanticField(
        default=0.9,
        description="Confidence score between 0.0 and 1.0.",
    )


class APIQueryDecompositionResponse(BaseModel):
    conditions: list[APIConditionItem] = PydanticField(
        description="List of extracted conditions from the query."
    )


def _error_code(error: Exception) -> str:
    """HTTP-style code of an API error (429, 503, 504...), or 'other'."""
    code = getattr(error, "code", None)
    if isinstance(code, int):
        return str(code)
    match = re.match(r"\s*(\d{3})\b", str(error))
    return match.group(1) if match else "other"


SYSTEM_PROMPT = """You are an expert B2B Search Query Decomposition Agent.
Your task is to break down a user's natural language search query (or its remaining unexplained parts) into structured conditions that can be matched against a company database.

Available company fields:
- Objective fields: year_founded, address, employee_count, revenue, is_public
- Semantic & taxonomy fields: primary_naics, description, core_offerings, target_markets, business_model

Rules:
1. GEOGRAPHIC EXPANSION: If the query mentions a region (e.g., "Scandinavia", "Balkans", "Europe"), expand it into a list of specific country names in `value_list` with operator `in` on field `address`.
2. SEMANTIC EXPANSION & ECOSYSTEM INTENT: If a query asks for companies that "could supply X for Y" or "compete with Z", infer the actual company profile:
   - What do they sell? Put expanded synonyms/products in `core_offerings` (operator `in`).
   - Who do they sell to? Put client industries in `target_markets` (operator `in`).
   - How do they operate? Put `B2B`, `B2C`, `SaaS`, `Manufacturer`, `Supplier`, etc. in `business_model`.
3. INDULGENT NAICS EXPANSION: Whenever the query implies an industry, sector, product, or service, generate a broad, indulgent list of relevant NAICS code prefixes (2 to 4 digits, e.g., "3254", "5417", "4242", "5132", "5415") covering all plausible sectors where such a company might be registered (e.g., manufacturing, R&D, wholesale, software, services). Put these numeric code prefixes as strings in `value_list` with operator `in` on field `primary_naics`.
4. DO NOT return conditions with operator `ignore`. Only return active conditions actually implied by the text provided.
"""


class APIConditionExtractor:
    """Phase 2: LLM-based extractor that translates remaining query intent into conditions."""

    def __init__(self):
        self.is_active = Config.has_api()
        if self.is_active:
            self.client = genai.Client(
                api_key=Config.API_KEY,
                http_options=types.HttpOptions(timeout=12000),
            )
            self.model_name = Config.MODEL_NAME

    def process(self, query: Query) -> Query:
        if not self.is_active or query.is_fully_explained:
            query.fill_phantom_conditions()
            return query

        user_prompt = (
            f"Query to analyze: \"{query.remainder}\"\n\n"
            "Extract all relevant conditions from the query."
        )

        # Campurile obiective deja extrase de Faza 1 (Local) nu trebuie suprascrise de API
        local_objective_fields = {
            c.field for c in query.active_conditions
            if c.source == "local" and c.field in {
                Field.YEAR_FOUNDED, Field.EMPLOYEE_COUNT, Field.REVENUE, Field.IS_PUBLIC, Field.ADDRESS
            }
        }

        try:
            query.api_called = True
            print(f"[DEBUG] -> Trimit request catre API (Model: {self.model_name}). Text analizat: '{query.remainder}'")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=APIQueryDecompositionResponse,
                    temperature=0.1,
                ),
            )

            parsed: APIQueryDecompositionResponse = response.parsed
            print("[DEBUG] -> Raspuns primit de la API cu succes!")

            if parsed and parsed.conditions:
                for item in parsed.conditions:
                    if item.operator == Operator.IGNORE:
                        continue
                    if item.field in local_objective_fields:
                        continue

                    actual_value = item.value_list if item.value_list is not None else item.value_string

                    if item.field in (Field.PRIMARY_NAICS, Field.SECONDARY_NAICS):
                        raw_naics = actual_value if isinstance(actual_value, list) else [str(actual_value)]
                        actual_value = [str(code).strip() for code in raw_naics if code and str(code).strip()]
                        if not actual_value:
                            continue
                    # Imbogatim tarile gasite de API cu orasele din dictionarul local (ex: Romania -> Brasov, Cluj)
                    if item.field == Field.ADDRESS and isinstance(actual_value, list):
                        expanded_geo = list(actual_value)
                        for loc in actual_value:
                            extra_cities = LocalConditionExtractor._GEO_EXPANSIONS.get(loc.lower(), [])
                            for city in extra_cities:
                                if city not in expanded_geo:
                                    expanded_geo.append(city)
                        actual_value = expanded_geo

                    cond = Condition(
                        field=item.field,
                        operator=item.operator,
                        value=actual_value,
                        source="api",
                        confidence=item.confidence,
                        span=None,
                    )
                    query.add_condition(cond)

        except Exception as e:
            query.api_error = _error_code(e)
            print(f"[WARN] Eroare API ({e}). Activam Brute-Mode Fallback pentru restul query-ului!")
            fallback_extractor = LocalConditionExtractor(brute_mode=True)
            occupied = [c.span for c in query.active_conditions if c.span is not None]
            fallback_extractor._extract_brute_mode_semantics(query, query.text, occupied)

        query.fill_phantom_conditions()
        return query