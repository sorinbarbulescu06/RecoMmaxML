import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from collections import Counter

from src.query.query import Query, Field, OBJECTIVE_FIELDS
from src.process.normalizer import AddressNormalizer


@dataclass
class ScoringConfig:
    """
    [FINE-TUNING CONFIG]
    Ponderile au fost ajustate pentru a prioritiza 'Ce vinde' in defavoarea lui 'Ce mentioneaza'.
    Datele obiective devin penalizari, iar scorul este complet continuu.
    """
    weight_semantic_core: float = 45.0      # Oferta reala a firmei (Semnalul cel mai bun)
    weight_semantic_markets: float = 15.0
    weight_semantic_desc: float = 10.0      # Descrierea generica devine secundara
    weight_naics: float = 30.0

    # Penalizari in loc de bonusuri
    penalty_missing_objectives: float = 15.0
    penalty_naics_mismatch: float = 15.0    # Penalizam daca firma opereaza dovedit in alt sector

    # Pragul minim pentru a intra in clasament (Prăpastia)
    min_score_threshold: float = 25.0


class SemanticScorer:
    """
    Motor de scorare semantic ponderat si normalizat pentru Etapa 2B.
    Ruleaza scoruri continue (Term Frequency) si normalizare reala raportata la cerintele query-ului.
    """

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

        # Calculam bugetul MAXIM activ al acestui query specific (pentru normalizare 100% corecta)
        self.active_max_weight = 0.0
        if self.q_offerings: self.active_max_weight += self.config.weight_semantic_core
        if self.q_markets: self.active_max_weight += self.config.weight_semantic_markets
        if self.q_desc: self.active_max_weight += self.config.weight_semantic_desc
        if self.q_naics_prefixes: self.active_max_weight += self.config.weight_naics
        
        if self.active_max_weight == 0.0:
            self.active_max_weight = 1.0 # Fallback 

    def _parse_query_intent(self) -> None:
        """Parseaza intentia si normalizeaza seturile de cuvinte cheie."""
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
        """
        Calculeaza scorul total normalizat [0..100] pentru o companie candidata.
        """
        # 1. Notare Semantica Continua (TF)
        score_offerings = self._score_field_continuous(
            company.get("core_offerings"), self.q_offerings, self.config.weight_semantic_core
        )
        score_desc = self._score_field_continuous(
            [company.get("description"), company.get("primary_naics")], self.q_desc, self.config.weight_semantic_desc
        )
        score_markets = self._score_field_continuous(
            company.get("target_markets"), self.q_markets, self.config.weight_semantic_markets
        )
        
        semantic_total = score_offerings + score_desc + score_markets

        # 2. NAICS Matching (Castig vs Penalizare Mismatch)
        naics_score = 0.0
        naics_penalty = 0.0
        company_naics = AddressNormalizer.extract_naics_codes(
            company.get("primary_naics"), company.get("secondary_naics")
        )
        
        if self.q_naics_prefixes:
            if company_naics:
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
                else:
                    # Are NAICS, dar nu se potriveste -> penalizare de mismatch
                    naics_penalty = self.config.penalty_naics_mismatch

        # 3. Penalizare pentru Date Obiective Lipsa (Null)
        objective_penalty = self._calculate_objective_penalty(company)

        # 4. Normalizarea Scorului Final
        raw_score = semantic_total + naics_score
        penalties = naics_penalty + objective_penalty
        
        # Procentaj din bugetul activ al query-ului
        normalized_score = (raw_score / self.active_max_weight) * 100.0
        
        # Aplicam penalizarile (fara sa scadem sub 0)
        final_score = max(0.0, normalized_score - penalties)

        # Pentru departajare absolut determinista, pastram si 3 zecimale, plus sortare alfabetica fallback
        final_score_rounded = round(final_score, 3)

        return {
            "operational_name": company.get("operational_name") or company.get("website", "Unknown"),
            "website": company.get("website"),
            "total_score": final_score_rounded,
            "breakdown": {
                "semantic_core_offerings": round(score_offerings, 3),
                "semantic_description": round(score_desc, 3),
                "semantic_target_markets": round(score_markets, 3),
                "naics_matching": round(naics_score, 3),
                "naics_penalty": round(naics_penalty, 3),
                "objective_penalty": round(objective_penalty, 3),
                "normalized_base_score": round(normalized_score, 3)
            }
        }

    def _score_field_continuous(self, company_field_val: Any, query_tokens: set[str], max_weight: float) -> float:
        """
        Calculeaza un scor continuu bazat pe cate cuvinte s-au potrivit (ca baza) 
        + o mica aditie pentru frecventa (Term Frequency) pentru a sparge egalitatile.
        """
        if not query_tokens or company_field_val is None:
            return 0.0
        
        # Extragem tokenii sub forma de lista (ca sa le numaram frecventa)
        comp_tokens_list = []
        if isinstance(company_field_val, list):
            for val in company_field_val:
                if val:
                    comp_tokens_list.extend(AddressNormalizer.tokenize_and_normalize(val))
        else:
            comp_tokens_list.extend(AddressNormalizer.tokenize_and_normalize(company_field_val))
            
        if not comp_tokens_list:
            return 0.0

        comp_tokens_set = set(comp_tokens_list)
        intersection = query_tokens.intersection(comp_tokens_set)
        
        if not intersection:
            return 0.0

        # Base score (raportul de acoperire al query-ului)
        base_ratio = len(intersection) / len(query_tokens)
        base_score = base_ratio * max_weight
        
        # Term Frequency Bonus (0.01 puncte pentru fiecare aparitie suplimentara a cuvintelor potrivite)
        tf_bonus = 0.0
        token_counts = Counter(comp_tokens_list)
        for token in intersection:
            count = token_counts[token]
            if count > 1:
                tf_bonus += (count - 1) * 0.01

        return min(max_weight, base_score + tf_bonus)

    def _calculate_objective_penalty(self, company: dict[str, Any]) -> float:
        """
        Daca firma are date lipsa (null) pe un camp obiectiv cerut activ, o penalizam proportional.
        """
        active_objs = [c for c in self.active_conditions if c.field in OBJECTIVE_FIELDS]
        if not active_objs:
            return 0.0

        missing_count = 0
        for cond in active_objs:
            field_name = cond.field.value
            val = company.get(field_name)
            if val is None:
                missing_count += 1

        # Daca 2 din 4 campuri cerute lipsesc, penalizarea este 50% din `penalty_missing_objectives`
        penalty_ratio = missing_count / len(active_objs)
        return penalty_ratio * self.config.penalty_missing_objectives


def rank_candidates(
    query: Query, 
    candidates_file_path: str | Path, 
    query_index: int = 1, 
    top_k: int = 5, 
    output_dir: str | Path = "top_results",
    telemetry_dir: str | Path = "assets/captured_data"
) -> list[dict[str, Any]]:
    """
    Citreste fisierul de candidati (.jsonl), aplica SemanticScorer, 
    filtreaza firmele sub un threshold de relevanta,
    salveaza Top-K intr-un director dedicat cu denumire dinamica 
    si exporta telemetria detaliata.
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
                    
                    # 6. Lista se opreste cand nu mai sunt firme bune (Prăpastia)
                    if result["total_score"] >= scorer.config.min_score_threshold:
                        scored_list.append((result, comp))
                except json.JSONDecodeError:
                    continue

    # Sortare in O(n log n) determinista (dupa scor descrescator, apoi dupa nume alfabetic)
    scored_list.sort(key=lambda x: (x[0]["total_score"], x[0]["operational_name"]), reverse=True)

    # 1. Creare director de output dinamic pentru Top-K
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    # Asiguram ca numim fisierul cu lungimea reala in caz ca pragul a taiat lista sub K
    actual_k = min(top_k, len(scored_list))
    top_k_filename = out_path / f"top_{actual_k}_query_{query_index}.jsonl"
    
    top_results = []
    with open(top_k_filename, "w", encoding="utf-8") as out_f:
        for score_dict, raw_comp in scored_list[:top_k]:
            top_results.append(score_dict)
            export_record = dict(raw_comp)
            export_record["scoring_result"] = score_dict
            out_f.write(json.dumps(export_record, ensure_ascii=False) + "\n")

    # 2. Generare telemetrie si statistici in assets/captured_data/
    tel_path = Path(telemetry_dir)
    tel_path.mkdir(parents=True, exist_ok=True)
    
    telemetry_filename = tel_path / f"telemetry_query_{query_index}.json"
    
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
        "total_candidates_above_threshold": total_scored,
        "score_statistics": {
            "max_score": max_score,
            "min_score": round(min_score, 3),
            "average_score": round(avg_score, 3)
        },
        "top_k_saved": actual_k,
        "output_file": str(top_k_filename),
        "full_candidates_breakdown": [item[0] for item in scored_list]
    }

    with open(telemetry_filename, "w", encoding="utf-8") as tel_f:
        json.dump(telemetry_data, tel_f, ensure_ascii=False, indent=2)

    return top_results