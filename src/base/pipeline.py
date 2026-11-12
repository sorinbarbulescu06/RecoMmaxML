import os

from src.query.query import Query
from src.query.local import LocalConditionExtractor
from src.query.call import APIConditionExtractor
from src.base.config import Config

class QueryQualificationPipeline:
    """
    'Mother class' that orchestrates the condition grepping phases:
    Initial Query -> Phase 1 (Local Agent) -> Phase 2 (API Call + Phantom Conditions).
    """

    def __init__(self):
        if not Config.has_api():
            print("\n" + "!" * 70)
            print("! AVERTISMENT: GEMINI_API_KEY was not found")
            print("! RUNNING ON BRUTE-MODE (WITHOUT API CALL).")
            print("!" * 70 + "\n")
        
        self.phase1 = LocalConditionExtractor()
        self.phase2 = APIConditionExtractor()

    def run(self, raw_query: str) -> Query:
        """Runs the full condition extraction pipeline on a user query string."""
        query = Query(text=raw_query)

        # Phase 1: Local deterministic extraction (currently TODO passthrough)
        query = self.phase1.process(query)

        # Phase 2: API intelligent extraction + Phantom conditions for unmentioned fields
        query = self.phase2.process(query)

        return query


if __name__ == "__main__":
    # Mic test rapid pe 2 query-uri din enunț (unul structurat, unul de ecosistem)
    pipeline = QueryQualificationPipeline()

    test_queries = [
        "Logistic companies in Romania",
        "Public software companies with more than 1,000 employees",
        "Food and beverage manufacturers in France",
        "Companies that could supply packaging materials for a direct-to-consumer cosmetics brand",
        "Construction companies in the United States with revenue over $50 million",
        "Pharmaceutical companies in Switzerland",
        "B2B SaaS companies providing HR solutions in Europe",
        "Clean energy startups founded after 2018 with fewer than 200 employees",
        "Fast-growing fintech companies competing with traditional banks in Europe.",
        "E-commerce companies using Shopify or similar platforms",
        "Renewable energy equipment manufacturers in Scandinavia",
        "Companies that manufacture or supply critical components for electric vehicle battery production",
    ]

    for q_text in test_queries:
        print("=" * 70)
        result_query = pipeline.run(q_text)
        print(f"QUERY: {result_query.text}\n")

        print("-> CONDITII ACTIVE (Ce cautam in baza de date):")
        for c in result_query.active_conditions:
            print(f"   [{c.source.upper()}] {c.field.value} {c.operator.value} {c.value} (conf={c.confidence:.2f})")

        print("\n-> CONDITII FANTOMA (Campuri marcate ca neimportante):")
        for c in result_query.phantom_conditions:
            print(f"   [PHANTOM] {c.field.value} -> {c.operator.value}")