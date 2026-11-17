import json
import os
import time
from datetime import datetime
from pathlib import Path

from src.query.query import Query
from src.query.local import LocalConditionExtractor
from src.query.call import APIConditionExtractor
from src.base.config import Config
from src.process.filter import HardFilterProcessor


class QueryQualificationPipeline:
    """
    'Mother class' that orchestrates the condition grepping phases:
    Initial Query -> Phase 1 (Local Agent) -> Phase 2 (API Call + Phantom Conditions)
    -> Phase 3 (Hard Filtering on dataset/companies.jsonl -> temp JSONL file).
    """

    def __init__(
        self,
        db_path: str | Path = "dataset/companies.jsonl",
        temp_dir: str | Path = "dataset/temp",
    ):
        if not Config.has_api():
            print("\n" + "!" * 70)
            print("! AVERTISMENT: GEMINI_API_KEY was not found")
            print("! RUNNING ON BRUTE-MODE (WITHOUT API CALL).")
            print("!" * 70 + "\n")

        self.phase2 = APIConditionExtractor()
        self.phase1 = LocalConditionExtractor(brute_mode=not self.phase2.is_active)
        self.db_path = Path(db_path)
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def run(self, raw_query: str) -> Query:
        """Runs the full condition extraction pipeline on a user query string."""
        query = Query(text=raw_query)

        # Phase 1: Local deterministic extraction
        t0 = time.perf_counter()
        query = self.phase1.process(query)
        query.local_ms = (time.perf_counter() - t0) * 1000

        # Phase 2: API intelligent extraction + Phantom conditions for unmentioned fields
        t0 = time.perf_counter()
        query = self.phase2.process(query)
        query.api_ms = (time.perf_counter() - t0) * 1000

        return query

    def filter_database(self, qualified_query: Query, query_index: int = 1) -> tuple[Path, int, int, int]:
        """
        Deschide dataset/companies.jsonl, ia fiecare firma linie cu linie si o trimite
        catre HardFilterProcessor (package-ul `process`).
        Returneaza (calea_fisierului_temp, total_vazute, total_trecute, total_excluse).
        """
        temp_file = self.temp_dir / f"candidates_q{query_index}.jsonl"

        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Nu am gasit baza de date la calea: {self.db_path.resolve()}"
            )

        with HardFilterProcessor(qualified_query, temp_file) as processor:
            with open(self.db_path, mode="r", encoding="utf-8") as db_file:
                for raw_line in db_file:
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    try:
                        company_dict = json.loads(stripped)
                    except json.JSONDecodeError:
                        continue

                    processor.process_company(company_dict, raw_json_line=stripped)

        return temp_file, processor.total_seen, processor.total_passed, processor.total_dropped


if __name__ == "__main__":
    pipeline = QueryQualificationPipeline(
        db_path="dataset/companies.jsonl",
        temp_dir="dataset/temp",
    )

    # Cele 12 query-uri principale (poti decomenta/adauga restul de 200 oricand)
    test_queries = [
        "Logistic companies in Romania",
        "Public software companies with more than 1,000 employees.",
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

    run_dir = Path("assets/runs")
    run_dir.mkdir(parents=True, exist_ok=True)
    run_log = run_dir / f"run_{datetime.now():%Y%m%d_%H%M%S}.jsonl"

    for idx, q_text in enumerate(test_queries, start=1):
        print("=" * 70)
        result_query = pipeline.run(q_text)
        print(f"QUERY #{idx}: {result_query.text}")
        print(f"STATUS: {result_query.status} | API called: {result_query.api_called} | "
              f"API error: {result_query.api_error} (retries: {result_query.api_retries}) | local: {result_query.local_ms:.1f} ms | "
              f"api: {result_query.api_ms:.0f} ms\n")
        if result_query.status == "failed":
            print("[WARN] Query not understood (no active conditions): no company is returned.\n")

        print("-> CONDITII ACTIVE (Ce cautam in baza de date):")
        for c in result_query.active_conditions:
            print(f"   [{c.source.upper()}] {c.field.value} {c.operator.value} {c.value} (conf={c.confidence:.2f})")

        print("\n-> CONDITII FANTOMA (Campuri marcate ca neimportante):")
        for c in result_query.phantom_conditions:
            print(f"   [PHANTOM] {c.field.value} -> {c.operator.value}")

        # Trierea Hard pe dataset/companies.jsonl -> dataset/temp/candidates_q{idx}.jsonl
        temp_path, seen, passed, dropped = pipeline.filter_database(result_query, query_index=idx)
        print(f"\n-> REZULTAT TRIERE HARD (Etapa 2A):")
        print(f"   Total firme in DB: {seen} | Calificate: {passed} | Excluse: {dropped}")
        print(f"   Fisier candidati:  {temp_path}")

        record = result_query.to_record()
        record.update(seen=seen, passed=passed, dropped=dropped)
        with open(run_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\nRun log: {run_log}")