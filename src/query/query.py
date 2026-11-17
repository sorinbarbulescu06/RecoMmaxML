import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Field(str, Enum):
    """Company fields a condition can refer to (fixed list, no free-text typos)."""
    YEAR_FOUNDED = "year_founded"
    ADDRESS = "address"
    EMPLOYEE_COUNT = "employee_count"
    REVENUE = "revenue"
    PRIMARY_NAICS = "primary_naics"
    SECONDARY_NAICS = "secondary_naics"
    DESCRIPTION = "description"
    BUSINESS_MODEL = "business_model"
    TARGET_MARKETS = "target_markets"
    CORE_OFFERINGS = "core_offerings"
    IS_PUBLIC = "is_public"

# Words that mean nothing as a filter on their own. The list is short on purpose:
# ignoring too much would skip the API call when it is actually needed.
IGNORED_WORDS = frozenset({
    "a", "an", "the", "of", "in", "on", "at", "for", "with", "by", "to", "from",
    "and", "or", "than", "that", "which", "who", "is", "are",
    "company", "companies", "firm", "firms",
})

OBJECTIVE_FIELDS = (
    Field.YEAR_FOUNDED,
    Field.ADDRESS,
    Field.EMPLOYEE_COUNT,
    Field.REVENUE,
    Field.IS_PUBLIC,
)


class Operator(str, Enum):
    EQ = "=="
    LT = "<"
    LTE = "<="
    GT = ">"
    GTE = ">="
    IN = "in"
    IGNORE = "ignore"  # Irelevant condition for query


@dataclass(frozen=True)
class Condition:
    """One self-contained piece of meaning extracted from a query,
    e.g. employee_count < 200, or a phantom condition (operator=IGNORE)."""
    field: Field
    operator: Operator
    value: Any = None
    source: str = "local"                     # "local", "api", or "phantom"
    confidence: float = 1.0                   # 0..1
    span: Optional[tuple[int, int]] = None    # (start, end) chars of the query it explains

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if self.span is not None and not 0 <= self.span[0] < self.span[1]:
            raise ValueError(f"invalid span {self.span}")

    @property
    def is_phantom(self) -> bool:
        """True if this condition marks a field as unimportant for the current query."""
        return self.operator == Operator.IGNORE

    def key(self):
        """Identity used to detect duplicates (ignores source/confidence/span)."""
        v = tuple(self.value) if isinstance(self.value, list) else self.value
        return (self.field, self.operator, v)


@dataclass
class Query:
    """A user query plus everything we managed to understand from it."""
    text: str
    conditions: list[Condition] = field(default_factory=list)

    # Notes filled in while the query goes through the pipeline
    api_called: bool = False
    api_error: Optional[str] = None   # "429", "503", "504", "other", or None if no error
    api_retries: int = 0              # how many times the call was repeated after a 429 / 503
    local_ms: float = 0.0
    api_ms: float = 0.0               # includes the local fallback when the API fails

    def __post_init__(self):
        if not self.text or not self.text.strip():
            raise ValueError("query text must not be empty")

    def add_condition(self, condition: Condition) -> bool:
        """Add a condition. Returns False if an identical one already exists."""
        if condition.span is not None and condition.span[1] > len(self.text):
            raise ValueError(f"span {condition.span} is outside the query text")
        if any(c.key() == condition.key() for c in self.conditions):
            return False
        self.conditions.append(condition)
        return True

    def fill_phantom_conditions(self) -> None:
        """Marks any unmentioned objective fields as phantom (unimportant) conditions."""
        mentioned_fields = {c.field for c in self.conditions}
        for obj_field in OBJECTIVE_FIELDS:
            if obj_field not in mentioned_fields:
                self.add_condition(
                    Condition(
                        field=obj_field,
                        operator=Operator.IGNORE,
                        value=None,
                        source="phantom",
                        confidence=1.0,
                    )
                )

    @property
    def active_conditions(self) -> list[Condition]:
        """Conditions that actually filter/rank companies."""
        return [c for c in self.conditions if not c.is_phantom]

    @property
    def phantom_conditions(self) -> list[Condition]:
        """Phantom conditions (fields explicitly ignored for this query)."""
        return [c for c in self.conditions if c.is_phantom]

    @property
    def remainder(self) -> str:
        """Text not covered by any condition's span, computed on the fly.
        This is the 'NU STIU' part: what is left for the API."""
        covered = [False] * len(self.text)
        for c in self.conditions:
            if c.span:
                for i in range(c.span[0], c.span[1]):
                    covered[i] = True
        left = "".join(ch if not covered[i] else " " for i, ch in enumerate(self.text))
        return " ".join(left.split())

    @property
    def is_fully_explained(self) -> bool:
        """True if nothing meaningful is left in the remainder (punctuation and
        IGNORED_WORDS don't count). The remainder text itself stays untouched,
        because the API needs words like 'for' for context."""
        words = re.findall(r"\w+", self.remainder.lower())
        return all(w in IGNORED_WORDS for w in words)

    @property
    def status(self) -> str:
        """failed: no active condition. partial: the API failed, only the local part is left.
        understood: everything else."""
        if not self.active_conditions:
            return "failed"
        if self.api_error:
            return "partial"
        return "understood"

    def to_record(self) -> dict:
        """One flat dict per query, to be written as a line in a .jsonl run log."""
        return {
            "query": self.text,
            "status": self.status,
            "api_called": self.api_called,
            "api_error": self.api_error,
            "api_retries": self.api_retries,
            "local_ms": round(self.local_ms, 2),
            "api_ms": round(self.api_ms, 2),
            "conditions": [
                {"field": c.field.value, "operator": c.operator.value, "value": c.value,
                 "source": c.source, "confidence": c.confidence}
                for c in self.active_conditions
            ],
        }