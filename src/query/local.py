from src.query.query import Query


class LocalConditionExtractor:
    """Phase 1: Fast, zero-cost local rule/regex extractor for obvious hard facts."""

    def process(self, query: Query) -> Query:
        """
        Extracts deterministic conditions from the query text and populates spans.
        Anything not matched stays in `query.remainder` for Phase 2 (API).
        """
        # TODO: Implement local condition grepping (e.g., regex for year_founded,
        # employee_count, revenue, is_public) and set `span=(start, end)` so
        # `query.remainder` shrinks before calling the API.
        return query