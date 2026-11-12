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
        return not self.remainder