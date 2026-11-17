from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path
import json

from src.query.query import Query, Condition, Field, OBJECTIVE_FIELDS
from src.process.normalizer import AddressNormalizer


@dataclass
class ScoringConfig:
    """
    [FINE-TUNING CONFIG]
    Bugetul total de 100 de puncte impartit pe categorii conform specificatiilor.
    """
    weight_semantic_core: float = 30.0
    weight_semantic_desc: float = 15.0
    weight_semantic_markets: float = 15.0
    weight_naics: float = 20.0
    weight_objectives: float = 10.0
    weight_consistency: float = 10.0
    
    # Penalizare pentru campurile obiective care au 'null' in firma cand query-ul le-a cerut activ
    null_objective_penalty_factor: float = 0.5


class SemanticScorer:
    """
    Motor de scorare semantic ponderat si normalizat pentru Etapa 2B.
    Trateaza mismatching writing, contextul si lipsa datelor prin penalizari proportionale.
    """

    def __init__(self, query: Query, config: Optional[ScoringConfig] = None):
        self.query = query
        self.config = config or ScoringConfig()
        
        # Extragem conditiile active si fantoma din query
        self.active_conditions = query.active_conditions
        self.phantom_conditions = query.phantom_conditions
        
        # Seturi de tokeni normalizati extrasi din query pentru comparatie rapida O(1)
        self.q_offerings: set[str] = set()
        self.q_markets: set[str] = set()
        self.q_desc: set[str] = set()
        self.q_naics_prefixes: list[str] = []
        
        self._parse_query_intent()

    def _parse_query_intent(self) -> None:
        """Parseaza si normalizeaza cerintele query-ului pe baza conditiilor active."""
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

        # Daca raman cuvinte in remainder-ul query-ului, le adaugam in descriere/oferte pentru context suplimentar
        if self.query.remainder:
            remainder_tokens = AddressNormalizer.tokenize_and_normalize(self.query.remainder)
            self.q_desc.update(remainder_tokens)

    def score_company(self, company: dict[str, Any]) -> dict[str, Any]:
        """
        Calculeaza scorul total normalizat [0..100] pentru o companie candidata.
        """
        # 1. Notarea Semantica (Max 60p)
        score_offerings = self._score_field_overlap(
            company.get("core_offerings"), self.q_offerings, self.config.weight_semantic_core
        )
        score_desc = self._score_field_overlap(
            [company.get("description"), company.get("primary_naics")], self.q_desc, self.config.weight_semantic_desc
        )
        score_markets = self._score_field_overlap(
            company.get("target_markets"), self.q_markets, self.config.weight_semantic_markets
        )
        semantic_total = score_offerings + score_desc + score_markets

        # 2. NAICS Matching (Max 20p)
        naics_score = 0.0
        company_naics = AddressNormalizer.extract_naics_codes(
            company.get("primary_naics"), company.get("secondary_naics")
        )
        if self.q_naics_prefixes and company_naics:
            match_found = False
            for c_code in company_naics:
                for q_prefix in self.q_naics_prefixes:
                    if c_code.startswith(q_prefix) or q_prefix.startswith(c_code):
                        match_found = True
                        break
                if match_found:
                    break
            if match_found:
                naics_score = self.config.weight_naics

        # 3. Matching pe Date Obiective (Max 10p)
        # Verificam cate campuri obiective ACTIVE (nu fantoma) a cerut query-ul vs ce detine firma
        objective_score = self._score_objective_fields(company)

        # 4. Coerenta si Consecventa (Max 10p)
        # Tokenii cheie ai ofertei trebuie sa se regaseasca in cel putin 3 campuri diferite (ex: naics label, offerings, description)
        consistency_score = self._score_consistency(company)

        # Insusurirea totala a punctajului brut
        raw_total = semantic_total + naics_score + objective_score + consistency_score
        
        # Normalizare finala garantata in [0.0, 100.0]
        final_score = round(max(0.0, min(100.0, raw_total)), 2)

        return {
            "operational_name": company.get("operational_name") or company.get("website", "Unknown"),
            "website": company.get("website"),
            "total_score": final_score,
            "breakdown": {
                "semantic_core_offerings": round(score_offerings, 2),
                "semantic_description": round(score_desc, 2),
                "semantic_target_markets": round(score_markets, 2),
                "naics_matching": round(naics_score, 2),
                "objective_fields": round(objective_score, 2),
                "coherence_consistency": round(consistency_score, 2),
            }
        }

    def _score_field_overlap(self, company_field_val: Any, query_tokens: set[str], max_weight: float) -> float:
        """Calculeaza procentul de potrivire a tokenilor (Jaccard-like orientat pe query) rezolvand typing mismatches."""
        if not query_tokens or company_field_val is None:
            return 0.0
        
        comp_tokens = AddressNormalizer.tokenize_and_normalize(company_field_val)
        if not comp_tokens:
            return 0.0

        intersection = query_tokens.intersection(comp_tokens)
        if not intersection:
            return 0.0

        ratio = len(intersection) / len(query_tokens)
        return ratio * max_weight

    def _score_objective_fields(self, company: dict[str, Any]) -> float:
        """
        Verifica campurile obiective active cerute de query. 
        Daca firma are date lipsa (null) pe un camp cerut activ, o penalizam proportional.
        """
        active_objs = [c for c in self.active_conditions if c.field in OBJECTIVE_FIELDS]
        if not active_objs:
            # Daca query-ul n-a cerut nicio conditie obiectiva, oferim punctajul maxim (beneficiu total)
            return self.config.weight_objectives

        matched_count = 0
        total_penalties = 0.0

        for cond in active_objs:
            field_name = cond.field.value
            val = company.get(field_name)
            if val is not None:
                matched_count += 1
            else:
                # Penalizare pentru camp null cand era cerut activ
                total_penalties += (self.config.weight_objectives / len(active_objs)) * self.config.null_objective_penalty_factor

        base_score = (matched_count / len(active_objs)) * self.config.weight_objectives
        return max(0.0, base_score - total_penalties)

    def _score_consistency(self, company: dict[str, Any]) -> float:
        """
        Verifica daca tokenii de oferta ai firmei apar trans-candidat in cel putin 3 campuri diferite:
        primary_naics (label), core_offerings, description.
        """
        if not self.q_offerings:
            return 0.0

        fields_to_check = [
            company.get("primary_naics"),
            company.get("core_offerings"),
            company.get("description"),
        ]
        
        hit_fields = 0
        for f_val in fields_to_check:
            if f_val is not None:
                f_tokens = AddressNormalizer.tokenize_and_normalize(f_val)
                if self.q_offerings.intersection(f_tokens):
                    hit_fields += 1

        # Daca se regaseste in 3 campuri, ia maximul (10p); in 2 campuri ia proportional; sub 2 ia 0.
        if hit_fields >= 3:
            return self.config.weight_consistency
        elif hit_fields == 2:
            return self.config.weight_consistency * 0.6
        return 0.0


def rank_candidates(
    query: Query, 
    candidates_file_path: str | Path, 
    query_index: int = 1, 
    top_k: int = 5, 
    output_dir: str | Path = "top_results",
    telemetry_dir: str | Path = "assets/captured_data"
) -> list[dict[str, Any]]:
    """
    Citreste fisierul de candidati, aplica SemanticScorer, salveaza Top-K intr-un director dedicat 
    cu denumire dinamica (ex: top_5_query_1.jsonl) si exporta telemetria/statistici detaliate 
    in assets/captured_data/ pentru analiza ulterioara.
    """
    path = Path(candidates_file_path)
    if not path.exists():
        return []

    scorer = SemanticScorer(query)
    scored_list = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    comp = json.loads(line)
                    result = scorer.score_company(comp)
                    scored_list.append((result, comp))
                except json.JSONDecodeError:
                    continue

    # Sortare in O(n log n) dupa scorul total descrescator
    scored_list.sort(key=lambda x: x[0]["total_score"], reverse=True)

    # 1. Creare director de output dinamic pentru Top-K
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    top_k_filename = out_path / f"top_{top_k}_query_{query_index}.jsonl"
    
    top_results = []
    with open(top_k_filename, "w", encoding="utf-8") as out_f:
        for score_dict, raw_comp in scored_list[:top_k]:
            top_results.append(score_dict)
            export_record = dict(raw_comp)
            export_record["scoring_result"] = score_dict
            out_f.write(json.dumps(export_record, ensure_ascii=False) + "\n")

    # 2. Generare telemetrie si statistici detaliate in assets/captured_data/
    tel_path = Path(telemetry_dir)
    tel_path.mkdir(parents=True, exist_ok=True)
    
    telemetry_filename = tel_path / f"telemetry_query_{query_index}.json"
    
    # Calculam cateva statistici agregate despre lotul de candidati scorati
    total_scored = len(scored_list)
    scores = [item[0]["total_score"] for item in scored_list] if scored_list else [0.0]
    avg_score = sum(scores) / total_scored if total_scored > 0 else 0.0
    max_score = max(scores) if scores else 0.0
    min_score = min(scores) if scores else 0.0

    telemetry_data = {
        "query_text": query.text,
        "query_status": query.status,
        "api_called": query.api_called,
        "api_error": query.api_error,
        "total_candidates_evaluated": total_scored,
        "score_statistics": {
            "max_score": max_score,
            "min_score": round(min_score, 2),
            "average_score": round(avg_score, 2)
        },
        "top_k_saved": len(top_results),
        "output_file": str(top_k_filename),
        "full_candidates_breakdown": [item[0] for item in scored_list]
    }

    with open(telemetry_filename, "w", encoding="utf-8") as tel_f:
        json.dump(telemetry_data, tel_f, ensure_ascii=False, indent=2)

    return top_results