import json
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import time
from datetime import datetime
from pathlib import Path
from contextlib import redirect_stdout

from src.query.query import Query
from src.query.local import LocalConditionExtractor
from src.query.call import APIConditionExtractor
from src.base.config import Config
from src.process.filter import HardFilterProcessor
from src.process.scorer import rank_candidates


class QueryQualificationPipeline:
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
        query = Query(text=raw_query)

        t0 = time.perf_counter()
        query = self.phase1.process(query)
        query.local_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        query = self.phase2.process(query)
        query.api_ms = (time.perf_counter() - t0) * 1000

        return query

    def filter_database(self, qualified_query: Query, query_index: int = 1) -> tuple[Path, int, int, int]:
        temp_file = self.temp_dir / f"candidates_q{query_index}.jsonl"

        if not self.db_path.exists():
            raise FileNotFoundError(f"Nu am gasit baza de date la calea: {self.db_path.resolve()}")

        seen_company_ids = set()
        total_seen_raw = 0

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

                    total_seen_raw += 1
                    
                    unique_id = str(company_dict.get("website") or company_dict.get("operational_name") or "").strip().lower()
                    if not unique_id or unique_id in seen_company_ids:
                        continue

                    seen_company_ids.add(unique_id)
                    processor.process_company(company_dict, raw_json_line=stripped)

        return temp_file, total_seen_raw, processor.total_passed, processor.total_dropped


def run_pipeline_logic(test_queries: list[str]):
    """
    Logica originala intacta. Primeste lista de query-uri si face toata treaba
    cu redirectarea fisierelor si scoring-ul.
    """
    pipeline = QueryQualificationPipeline(
        db_path="dataset/companies.jsonl",
        temp_dir="dataset/temp",
    )

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_out_dir = Path("results") / run_timestamp
    
    company_lists_dir = base_out_dir / "company_lists"
    telemetry_list_dir = base_out_dir / "telemetry_list"
    company_lists_dir.mkdir(parents=True, exist_ok=True)
    telemetry_list_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = base_out_dir / "log.txt"
    top_file = base_out_dir / "top.txt"
    query_list_file = base_out_dir / "query_list.jsonl"

    for idx, q_text in enumerate(test_queries, start=1):
        
        with open(log_file, "a", encoding="utf-8") as f_log:
            with redirect_stdout(f_log):
                print("=" * 70)
                result_query = pipeline.run(q_text)
                print(f"QUERY #{idx}: {result_query.text}")
                print(f"STATUS: {result_query.status} | API called: {result_query.api_called} | "
                      f"API error: {result_query.api_error} (retries: {result_query.api_retries}) | local: {result_query.local_ms:.1f} ms | "
                      f"api: {result_query.api_ms:.0f} ms\n")
                
                if result_query.status == "failed":
                    print("[WARN] Query not understood (no active conditions): no company is returned.\n")

                print("-> ACTIVE CONDITIONS (searching tokens):")
                for c in result_query.active_conditions:
                    print(f"   [{c.source.upper()}] {c.field.value} {c.operator.value} {c.value} (conf={c.confidence:.2f})")

                print("\n-> PHANTOM CONDITIONS (Unimportant fields):")
                for c in result_query.phantom_conditions:
                    print(f"   [PHANTOM] {c.field.value} -> {c.operator.value}")

                temp_path, seen, passed, dropped = pipeline.filter_database(result_query, query_index=idx)
                print(f"\n-> RESULTS HARD KNOCKOUT (STAGE 2A):")
                print(f"   Total companies in DB: {seen} | Calificated: {passed} | Dismissed: {dropped}")
                print(f"   Contestants file:  {temp_path}")

                K = 20
                top_companies = rank_candidates(
                    result_query, 
                    temp_path, 
                    query_index=idx, 
                    top_k=K, 
                    output_dir=company_lists_dir,
                    telemetry_dir=telemetry_list_dir
                )
                print(f"   [SCORING] Saved top_{K}_query_{idx}.jsonl in '{company_lists_dir}'")
                print(f"   [TELEMETRY] Saved detailed statistics in '{telemetry_list_dir}'\n")

        # Afisarea curata ceruta in terminal si in top.txt (Fara scor matematic)
        output_str = f"[{idx}/{len(test_queries)}] {result_query.text}\n"
        
        if top_companies:
            for i, comp in enumerate(top_companies, 1):
                name = comp.get('operational_name', 'N/A')
                website = comp.get('website', 'N/A')
                output_str += f"   {i}. {name:<40} | Web: {website}\n"
        else:
            output_str += f"   -> [INFO] No company reached the minimum threshold of relevance.\n"
        
        output_str += "-" * 70 + "\n"
        
        print(output_str, end="")
        
        with open(top_file, "a", encoding="utf-8") as f_top:
            f_top.write(output_str)

        log_entry = {
            "query_index": idx,
            "text": result_query.text,
            "status": result_query.status,
            "api_called": result_query.api_called,
            "api_error": result_query.api_error,
            "local_ms": round(result_query.local_ms, 2),
            "api_ms": round(result_query.api_ms, 2),
            "candidates_found": passed,
            "top_k_returned": len(top_companies)
        }
        with open(query_list_file, "a", encoding="utf-8") as f_qlist:
            f_qlist.write(json.dumps(log_entry, ensure_ascii=False) + "\n")