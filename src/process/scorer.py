import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from collections import Counter

from src.query.query import Query, Field, OBJECTIVE_FIELDS
from src.process.normalizer import AddressNormalizer


@dataclass
class ScoringConfig:
    weight_semantic_core: float = 45.0      
    weight_semantic_markets: float = 15.0
    weight_semantic_desc: float = 10.0      
    weight_naics: float = 30.0

    # Penalizari 
    penalty_missing_objectives: float = 15.0
    penalty_naics_mismatch: float = 15.0    
    penalty_null_core: float = 10.0         
    penalty_consumer_role: float = 5.0      # REDUS: de la 15.0 la 5.0 pentru a nu distruge SaaS-urile care fac integrari

    # Dynamic Thresholding
    min_score_threshold: float = 25.0       
    dynamic_threshold_ratio: float = 0.5    
    
    # Plafonul Maxim pentru Semantic overlap
    max_required_tokens: int = 3            # Daca a nimerit 3 tokeni principali, ia punctajul maxim


class SemanticScorer:
    def __init__(self, query: Query, config: Optional[ScoringConfig] = None):
        self.query = query
        self.config = config or ScoringConfig()
        
        self.active_conditions = query.active_conditions
        self.phantom_conditions = query.phantom_conditions
        
        self.q_offerings: set[str] = set()
        self.q_markets: set[str] = set()
        self.q_desc: set[str] = set()
        self.q_naics_prefixes: list[str] = []
        
        self._parse_query_intent()

        self.active_max_weight = 0.0
        if self.q_offerings: self.active_max_weight += self.config.weight_semantic_core
        if self.q_markets: self.active_max_weight += self.config.weight_semantic_markets
        if self.q_desc: self.active_max_weight += self.config.weight_semantic_desc
        if self.q_naics_prefixes: self.active_max_weight += self.config.weight_naics
        
        if self.active_max_weight == 0.0:
            self.active_max_weight = 1.0 

        # Lexicon Negativ CONTEXTUAL (Regex)
        # Nu mai penalizeaza cuvantul simplu, ci fraza de consumator.
        self.consumer_regexes = [
            re.compile(r'\buses\s+\w+\s+(software|platform|system)\b', re.IGNORECASE),
            re.compile(r'\bpowered\s+by\s+\w+\b', re.IGNORECASE),
            re.compile(r'\bclient\s+of\b', re.IGNORECASE),
            re.compile(r'\bcustomer\s+of\b', re.IGNORECASE)
        ]

    def _parse_query_intent(self) -> None:
        for cond in self.active_conditions:
            if cond.field == Field.CORE_OFFERINGS:
                self.q_offerings.update(AddressNormalizer.tokenize_and_normalize(cond.value))
            elif cond.field == Field.TARGET_MARKETS:
                self.q_markets.update(AddressNormalizer.tokenize_and_normalize(cond.value))
            elif cond.field == Field.DESCRIPTION:
                self.q_desc.update(AddressNormalizer.tokenize_and_normalize(cond.value))
            elif cond.field in (Field.PRIMARY_NAICS, Field.SECONDARY_NAICS):
                vals = cond.value if isinstance(cond.value, list) else [cond.value]
                for v in vals:
                    digits = AddressNormalizer.extract_naics_codes(v)
                    self.q_naics_prefixes.extend(digits)

    def score_company(self, company: dict[str, Any]) -> dict[str, Any]:
        # 1. Extragere tokeni si calcul bonus de densitate (CRESCUT pentru a fi vizibil)
        all_text = " ".join(filter(None, [
            company.get("core_offerings") if isinstance(company.get("core_offerings"), str) else " ".join(company.get("core_offerings", []) or []),
            company.get("description"),
            company.get("target_markets") if isinstance(company.get("target_markets"), str) else " ".join(company.get("target_markets", []) or [])
        ]))
        comp_all_tokens = AddressNormalizer.tokenize_and_normalize(all_text)
        
        # Spor vizibil (ex: 30 tokeni unici = +1.5 puncte)
        density_bonus = len(set(comp_all_tokens)) * 0.05

        # 2. Notare Semantica Continua
        score_offerings = self._score_field_continuous(company.get("core_offerings"), self.q_offerings, self.config.weight_semantic_core)
        score_desc = self._score_field_continuous([company.get("description"), company.get("primary_naics")], self.q_desc, self.config.weight_semantic_desc)
        score_markets = self._score_field_continuous(company.get("target_markets"), self.q_markets, self.config.weight_semantic_markets)
        
        semantic_total = score_offerings + score_desc + score_markets + density_bonus

        # 3. NAICS Matching
        naics_score = 0.0
        naics_penalty = 0.0
        company_naics = AddressNormalizer.extract_naics_codes(company.get("primary_naics"), company.get("secondary_naics"))
        
        if self.q_naics_prefixes:
            if company_naics:
                match_found = any(
                    c_code.startswith(q_prefix) or q_prefix.startswith(c_code)
                    for c_code in company_naics for q_prefix in self.q_naics_prefixes
                )
                if match_found:
                    naics_score = self.config.weight_naics
                else:
                    naics_penalty = self.config.penalty_naics_mismatch

        # 4. Penalizari Activa (Null Core, Obiective, Lexicon Consumator Contextual)
        objective_penalty = self._calculate_objective_penalty(company)
        
        null_core_penalty = 0.0
        if not company.get("core_offerings"):
            null_core_penalty = self.config.penalty_null_core
            
        role_penalty = 0.0
        raw_desc = str(company.get("description") or "")
        # Evaluare pe baza de regex, nu simplu 'in' string
        for pattern in self.consumer_regexes:
            if pattern.search(raw_desc):
                role_penalty = self.config.penalty_consumer_role
                break

        # 5. Calcul Final Normalizat
        raw_score = semantic_total + naics_score
        penalties = naics_penalty + objective_penalty + null_core_penalty + role_penalty
        
        normalized_score = (raw_score / self.active_max_weight) * 100.0
        final_score = max(0.0, normalized_score - penalties)

        # Asiguram ca niciun scor normalizat (fara penalizari) nu sare artificial peste 100.0
        final_score = min(100.0, final_score)

        return {
            "operational_name": company.get("operational_name") or company.get("website", "Unknown"),
            "website": company.get("website"),
            "total_score": round(final_score, 4),
            "breakdown": {
                "semantic_core_offerings": round(score_offerings, 3),
                "semantic_description": round(score_desc, 3),
                "semantic_target_markets": round(score_markets, 3),
                "density_bonus": round(density_bonus, 4),
                "naics_matching": round(naics_score, 3),
                "naics_penalty": round(naics_penalty, 3),
                "objective_penalty": round(objective_penalty, 3),
                "null_core_penalty": round(null_core_penalty, 3),
                "role_penalty": round(role_penalty, 3)
            }
        }

    def _score_field_continuous(self, company_field_val: Any, query_tokens: set[str], max_weight: float) -> float:
        if not query_tokens or not company_field_val:
            return 0.0
        
        comp_tokens_list = []
        if isinstance(company_field_val, list):
            for val in filter(None, company_field_val):
                comp_tokens_list.extend(AddressNormalizer.tokenize_and_normalize(val))
        else:
            comp_tokens_list.extend(AddressNormalizer.tokenize_and_normalize(company_field_val))
            
        if not comp_tokens_list:
            return 0.0

        intersection = query_tokens.intersection(set(comp_tokens_list))
        if not intersection:
            return 0.0

        # PLAFONUL MAXIM: Baza raportului nu este obligatoriu len(query_tokens)
        # Daca a nimerit un numar satisfacator de keywords (ex: 3), primeste punctajul integral
        effective_query_len = min(len(query_tokens), self.config.max_required_tokens)
        
        # Scorul de baza plafonat la max_weight
        base_score = min((len(intersection) / effective_query_len) * max_weight, max_weight)
        
        tf_bonus = 0.0
        token_counts = Counter(comp_tokens_list)
        for token in intersection:
            if token_counts[token] > 1:
                tf_bonus += (token_counts[token] - 1) * 0.005

        return min(max_weight, base_score + tf_bonus)

    def _calculate_objective_penalty(self, company: dict[str, Any]) -> float:
        active_objs = [c for c in self.active_conditions if c.field in OBJECTIVE_FIELDS]
        if not active_objs:
            return 0.0

        missing_count = sum(1 for cond in active_objs if company.get(cond.field.value) is None)
        return (missing_count / len(active_objs)) * self.config.penalty_missing_objectives


def rank_candidates(
    query: Query, 
    candidates_file_path: str | Path, 
    query_index: int = 1, 
    top_k: int = 20, 
    output_dir: str | Path = "top_results",
    telemetry_dir: str | Path = "assets/captured_data"
) -> list[dict[str, Any]]:
    path = Path(candidates_file_path)
    if not path.exists():
        return []

    scorer = SemanticScorer(query)
    
    all_scored = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    comp = json.loads(line)
                    all_scored.append((scorer.score_company(comp), comp))
                except json.JSONDecodeError:
                    continue

    if not all_scored:
        return []

    max_score_achieved = max(item[0]["total_score"] for item in all_scored)
    dynamic_cutoff = max(scorer.config.min_score_threshold, max_score_achieved * scorer.config.dynamic_threshold_ratio)

    scored_list = [item for item in all_scored if item[0]["total_score"] >= dynamic_cutoff]
    scored_list.sort(key=lambda x: (x[0]["total_score"], x[0]["operational_name"]), reverse=True)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    actual_k = min(top_k, len(scored_list))
    top_k_filename = out_path / f"top_{actual_k}_query_{query_index}.jsonl"
    
    top_results = []
    with open(top_k_filename, "w", encoding="utf-8") as out_f:
        for score_dict, raw_comp in scored_list[:top_k]:
            top_results.append(score_dict)
            export_record = dict(raw_comp)
            export_record["scoring_result"] = score_dict
            out_f.write(json.dumps(export_record, ensure_ascii=False) + "\n")

    tel_path = Path(telemetry_dir)
    tel_path.mkdir(parents=True, exist_ok=True)
    telemetry_filename = tel_path / f"telemetry_query_{query_index}.json"
    
    scores = [item[0]["total_score"] for item in scored_list] if scored_list else [0.0]
    
    telemetry_data = {
        "query_text": query.text,
        "query_status": query.status,
        "api_called": query.api_called,
        "total_candidates_above_threshold": len(scored_list),
        "dynamic_cutoff_applied": round(dynamic_cutoff, 3),
        "score_statistics": {
            "max_score": round(max_score_achieved, 3),
            "min_score": round(min(scores), 3) if scores else 0.0,
            "average_score": round(sum(scores) / len(scores), 3) if scores else 0.0
        },
        "top_k_saved": actual_k,
        "output_file": str(top_k_filename),
        "full_candidates_breakdown": [item[0] for item in scored_list]
    }

    with open(telemetry_filename, "w", encoding="utf-8") as tel_f:
        json.dump(telemetry_data, tel_f, ensure_ascii=False, indent=2)

    return top_results