import os
from pydantic import BaseModel, Field as PydanticField
from typing import Optional
from google import genai
from google.genai import types

from src.query.query import Condition, Field, Operator, Query
from src.base.config import Config


class ExtractedConditionSchema(BaseModel):
    field: Field = PydanticField(
        description="The target company field. Never use website."
    )
    operator: Operator = PydanticField(
        description=(
            "Comparison operator. Use '==', '<', '<=', '>', '>=' for numbers/booleans. "
            "Use 'in' when providing a list of normalized locations, keywords, offerings, or NAICS labels."
        )
    )
    # Am inlocuit acel Union cu doua campuri separate pentru ca schema API sa nu mai crape
    value_string: Optional[str] = PydanticField(
        default=None,
        description="Use this for single values (e.g. '1000', 'true', 'B2B'). Convert numbers/booleans to strings."
    )
    value_list: Optional[list[str]] = PydanticField(
        default=None,
        description="Use this for lists of values (e.g. ['Sweden', 'Norway'], ['packaging', 'bottles']) when using the 'in' operator."
    )
    confidence: float = PydanticField(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0."
    )


class APIQueryDecompositionResponse(BaseModel):
    conditions: list[ExtractedConditionSchema]


SYSTEM_PROMPT = """You are an expert Query Qualification & Decomposition Engine.
Your task is to break down a user search query looking for companies into structured atomic conditions.

Follow these strict rules:
1. OBJECTIVE CONSTRAINTS (Hard Facts):
   - Extract explicit constraints for `year_founded`, `employee_count`, `revenue`, `is_public`, and `address` ONLY if mentioned or strongly implied in the query.
   - Geographic Normalization: If a region is mentioned (e.g., "Scandinavia", "Europe", "Romania", "Balkans"), use `field="address"`, `operator="in"`, and expand `value_list` into a list of relevant country names(or important cities) and major hubs.

2. SUBJECTIVE / ECOSYSTEM CONSTRAINTS (Keywords & Meaning):
   - Translate industry roles, supply chain relationships, and vague criteria into concrete keyword lists (`operator="in"` and fill `value_list`).
   - Map products/services to `core_offerings` (e.g., ["packaging materials", "cosmetic containers"]).
   - Map customer segments to `target_markets` (e.g., ["cosmetics", "beauty", "direct-to-consumer"]).
   - Map general activity/ecosystem keywords to `description`.
"""


class APIConditionExtractor:
    """Phase 2: LLM-based extractor that translates remaining query intent into conditions."""

    def __init__(self):
        self.is_active = Config.has_api()
        if self.is_active:
            self.client = genai.Client(api_key=Config.API_KEY)
            self.model_name = Config.MODEL_NAME

    def process(self, query: Query) -> Query:
        if not self.is_active:
            query.fill_phantom_conditions()
            return query

        if query.is_fully_explained:
            query.fill_phantom_conditions()
            return query

        already_extracted = [
            f"{c.field.value} {c.operator.value} {c.value}"
            for c in query.active_conditions
        ]

        user_prompt = (
            f"Query to analyze: \"{query.remainder}\"\n\n"
            "Extract all relevant conditions from the query."
        )
        #todel
        print(f"[DEBUG] -> Trimit request catre API (Model: {self.model_name}). Asteptam raspuns...")

        try:
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
            #todel
            print("[DEBUG] -> Raspuns primit de la API cu succes!")
            parsed: APIQueryDecompositionResponse = response.parsed

            if parsed and parsed.conditions:
                #todel
                print(f"[DEBUG] -> API-ul a extras {len(parsed.conditions)} conditii.")
                for item in parsed.conditions:
                    if item.operator == Operator.IGNORE:
                        continue

                    # Determinam care valoare a fost completata de LLM
                    actual_value = item.value_list if item.value_list is not None else item.value_string

                    cond = Condition(
                        field=item.field,
                        operator=item.operator,
                        value=actual_value,
                        source="api",
                        confidence=item.confidence,
                        span=None,
                    )
                    query.add_condition(cond)
            #todel
            else:
                #todel
                print("[DEBUG] -> API-ul a raspuns, dar nu a gasit nicio conditie.")
        except Exception as e:
            print(f"Eroare la apelul API Gemini: {e}")

        #todel
        print("[DEBUG] -> Adaugam conditiile fantoma si iesim...")
        # Adăugăm condițiile fantomă pentru câmpurile obiective nemenționate
        query.fill_phantom_conditions()
        return query