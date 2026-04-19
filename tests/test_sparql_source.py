from wxyc_catalog.sources.sparql import SparqlSource


class TestSparqlSourceQueryExecution:
    """SparqlSource should execute SPARQL queries and parse results."""

    async def test_query_returns_bindings(self, httpx_mock):
        """query() should return the bindings array from SPARQL JSON response."""
        sparql_response = {
            "results": {
                "bindings": [
                    {
                        "item": {
                            "type": "uri",
                            "value": "http://www.wikidata.org/entity/Q2774",
                        },
                        "itemLabel": {"type": "literal", "value": "Autechre"},
                    },
                ]
            }
        }
        httpx_mock.add_response(json=sparql_response)

        source = SparqlSource(
            sparql_endpoint="https://query.wikidata.org/sparql",
            rate_limit=1000,
        )
        bindings = await source.query("SELECT ?item ?itemLabel WHERE { ?item wdt:P1953 '14' }")
        assert len(bindings) == 1
        assert bindings[0]["item"]["value"] == "http://www.wikidata.org/entity/Q2774"
        await source.close()

    async def test_empty_results(self, httpx_mock):
        """query() should return empty list when no results match."""
        httpx_mock.add_response(json={"results": {"bindings": []}})

        source = SparqlSource(rate_limit=1000)
        bindings = await source.query("SELECT ?item WHERE { ?item wdt:P1953 '999999' }")
        assert bindings == []
        await source.close()

    async def test_query_failure_returns_empty(self, httpx_mock):
        """query() should return empty list on HTTP failure."""
        httpx_mock.add_response(status_code=500)

        source = SparqlSource(rate_limit=1000)
        bindings = await source.query("SELECT ?item WHERE { ?item wdt:P31 wd:Q5 }")
        assert bindings == []
        await source.close()


class TestSparqlSourceQidValidation:
    """SparqlSource QID validation should accept Q-prefixed numbers only."""

    def test_valid_qids(self):
        source = SparqlSource(rate_limit=1000)
        valid = source.validate_qids(["Q1", "Q2774", "Q12345678"])
        assert valid == ["Q1", "Q2774", "Q12345678"]

    def test_invalid_qids_filtered(self):
        source = SparqlSource(rate_limit=1000)
        valid = source.validate_qids(["Q2774", "P1953", "invalid", "", "Q1"])
        assert valid == ["Q2774", "Q1"]

    def test_empty_input(self):
        source = SparqlSource(rate_limit=1000)
        assert source.validate_qids([]) == []


class TestSparqlSourceHelpers:
    """SparqlSource static helper methods."""

    def test_extract_qid_from_uri(self):
        assert SparqlSource.extract_qid("http://www.wikidata.org/entity/Q2774") == "Q2774"

    def test_extract_qid_from_bare_qid(self):
        assert SparqlSource.extract_qid("Q2774") == "Q2774"

    def test_binding_value_present(self):
        binding = {"item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q2774"}}
        assert SparqlSource.binding_value(binding, "item") == "http://www.wikidata.org/entity/Q2774"

    def test_binding_value_absent(self):
        binding = {"item": {"type": "uri", "value": "..."}}
        assert SparqlSource.binding_value(binding, "missing") is None


class TestSparqlSourceBatchSplitting:
    """SparqlSource should split large QID lists into batched VALUES clauses."""

    async def test_batch_splitting(self, httpx_mock):
        """Large QID lists should be split into batches."""
        sparql_response = {"results": {"bindings": []}}
        httpx_mock.add_response(json=sparql_response)
        httpx_mock.add_response(json=sparql_response)

        source = SparqlSource(batch_size=2, rate_limit=1000)
        await source.query_batched(
            "SELECT ?item WHERE {{ VALUES ?item {{ {values} }} ?item wdt:P31 wd:Q5 }}",
            ["Q1", "Q2", "Q3"],
        )
        # Should have made 2 requests (batch of 2 + batch of 1)
        assert len(httpx_mock.get_requests()) == 2
        await source.close()

    async def test_batch_results_combined(self, httpx_mock):
        """Results from all batches should be combined."""
        httpx_mock.add_response(
            json={
                "results": {
                    "bindings": [
                        {
                            "item": {
                                "type": "uri",
                                "value": "http://www.wikidata.org/entity/Q1",
                            }
                        },
                    ]
                }
            }
        )
        httpx_mock.add_response(
            json={
                "results": {
                    "bindings": [
                        {
                            "item": {
                                "type": "uri",
                                "value": "http://www.wikidata.org/entity/Q3",
                            }
                        },
                    ]
                }
            }
        )

        source = SparqlSource(batch_size=2, rate_limit=1000)
        results = await source.query_batched(
            "SELECT ?item WHERE {{ VALUES ?item {{ {values} }} ?item wdt:P31 wd:Q5 }}",
            ["Q1", "Q2", "Q3"],
        )
        assert len(results) == 2
        await source.close()

    async def test_batch_validates_qids(self, httpx_mock):
        """query_batched should filter invalid QIDs before batching."""
        sparql_response = {"results": {"bindings": []}}
        httpx_mock.add_response(json=sparql_response)

        source = SparqlSource(batch_size=50, rate_limit=1000)
        await source.query_batched(
            "SELECT ?item WHERE {{ VALUES ?item {{ {values} }} }}",
            ["Q1", "invalid", "Q2"],
        )
        # Only valid QIDs should be in the request
        request = httpx_mock.get_requests()[0]
        query_param = str(request.url)
        assert "invalid" not in query_param
        await source.close()
