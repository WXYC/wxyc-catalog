"""SPARQL query executor with result parsing, QID validation, and batch splitting.

Extends :class:`HttpSource` with:
- SPARQL query execution via GET with ``Accept: application/sparql-results+json``
- Result binding extraction from the standard SPARQL JSON response format
- QID format validation (Q followed by digits)
- Batch splitting: large QID lists are chunked into VALUES clauses
- User-Agent header (required by Wikidata)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from wxyc_catalog.sources.http import HttpSource

logger = logging.getLogger(__name__)

_QID_RE = re.compile(r"^Q\d+$")


class SparqlSource(HttpSource):
    """SPARQL query executor with result parsing, QID validation, and batch splitting.

    Args:
        sparql_endpoint: SPARQL endpoint URL.
        user_agent: User-Agent header value (required by Wikidata).
        batch_size: Maximum number of QIDs per VALUES clause in batched queries.
        rate_limit: Requests per ``rate_window`` (default: 1 req/sec for Wikidata).
        rate_window: Time window in seconds for the rate limit.
        **kwargs: Additional arguments passed to :class:`HttpSource`.
    """

    def __init__(
        self,
        sparql_endpoint: str = "https://query.wikidata.org/sparql",
        *,
        user_agent: str = "WXYCSemanticIndex/0.1 (https://wxyc.org; engineering@wxyc.org)",
        batch_size: int = 50,
        rate_limit: float = 1.0,
        rate_window: float = 1.0,
        **kwargs: Any,
    ) -> None:
        headers = kwargs.pop("headers", None) or {}
        headers.setdefault("User-Agent", user_agent)
        headers.setdefault("Accept", "application/sparql-results+json")
        super().__init__(
            base_url=sparql_endpoint,
            rate_limit=rate_limit,
            rate_window=rate_window,
            headers=headers,
            **kwargs,
        )
        self._batch_size = batch_size

    async def query(self, sparql: str) -> list[dict]:
        """Execute a SPARQL query and return the result bindings.

        Args:
            sparql: SPARQL query string.

        Returns:
            List of binding dicts from the SPARQL JSON response, or an empty
            list on failure.
        """
        response = await self.get("", params={"query": sparql})
        if response is None:
            return []
        try:
            data = response.json()
            return data["results"]["bindings"]
        except Exception:
            logger.warning("Failed to parse SPARQL response", exc_info=True)
            return []

    async def query_batched(
        self, sparql_template: str, qids: list[str], placeholder: str = "{values}"
    ) -> list[dict]:
        """Execute a SPARQL query in batches, splitting QIDs into VALUES clauses.

        Invalid QIDs are filtered out before batching.

        Args:
            sparql_template: SPARQL query template with a ``{values}`` placeholder.
            qids: List of Wikidata QIDs to query.
            placeholder: Placeholder string in the template (default ``"{values}"``).

        Returns:
            Combined list of bindings from all batch results.
        """
        valid = self.validate_qids(qids)
        if not valid:
            return []

        all_bindings: list[dict] = []
        for i in range(0, len(valid), self._batch_size):
            batch = valid[i : i + self._batch_size]
            values_clause = " ".join(f"wd:{qid}" for qid in batch)
            sparql = sparql_template.replace(placeholder, values_clause)
            bindings = await self.query(sparql)
            all_bindings.extend(bindings)

        return all_bindings

    def validate_qids(self, qids: list[str]) -> list[str]:
        """Filter a list of strings to only valid Wikidata QIDs (``Q`` followed by digits).

        Args:
            qids: List of candidate QID strings.

        Returns:
            Filtered list containing only valid QIDs, preserving order.
        """
        return [qid for qid in qids if _QID_RE.match(qid)]

    @staticmethod
    def extract_qid(uri: str) -> str:
        """Extract a QID from a Wikidata entity URI or bare QID string.

        Args:
            uri: A string like ``"http://www.wikidata.org/entity/Q2774"`` or ``"Q2774"``.

        Returns:
            The QID portion (e.g., ``"Q2774"``).
        """
        return uri.rsplit("/", 1)[-1]

    @staticmethod
    def binding_value(binding: dict, key: str) -> str | None:
        """Extract the ``value`` field from a SPARQL binding, or ``None`` if absent.

        Args:
            binding: A single binding dict from a SPARQL response.
            key: The variable name to look up.

        Returns:
            The string value, or ``None`` if the key is not present.
        """
        entry = binding.get(key)
        if entry is None:
            return None
        return entry.get("value")
