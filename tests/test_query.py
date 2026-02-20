"""
Tests for the AI Sales Query Agent API.

These tests use mocked LLM responses so they can run without
any API key or external service.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from mcp_server import execute_query

client = TestClient(app)


# --- Mock LLM response helper ---

MOCK_SQL_COUNT_CUSTOMERS = "SELECT COUNT(*) AS total_customers FROM customers"
MOCK_SQL_REVENUE = (
    "SELECT ROUND(SUM(p.price * oi.quantity), 2) AS total_revenue "
    "FROM products p JOIN order_items oi ON p.id = oi.product_id "
    "WHERE p.category = 'Technology'"
)


def _mock_process_question_count(question: str) -> dict:
    """Mock that returns a customer count query result."""
    from mcp_server import execute_query

    results = execute_query(MOCK_SQL_COUNT_CUSTOMERS)
    first_row = results[0] if results else {}
    label_key = list(first_row.keys())[0] if first_row else "total_customers"
    value = first_row.get(label_key, 0)

    return {
        "sql": MOCK_SQL_COUNT_CUSTOMERS,
        "results": results,
        "chart_data": {
            "labels": [str(label_key)],
            "values": [float(value)],
        },
    }


def _mock_process_question_unanswerable(question: str) -> dict:
    """Mock that raises ValueError for unanswerable questions."""
    raise ValueError(
        "This question cannot be answered using the available database schema."
    )


# --- Tests ---


class TestQueryEndpoint:
    """Tests for the POST /query endpoint."""

    @patch("main.process_question", side_effect=_mock_process_question_count)
    def test_query_endpoint_returns_200(self, mock_pq):
        """POST /query with a valid question returns 200 with expected keys."""
        response = client.post(
            "/query",
            json={"question": "How many customers are there?"},
        )
        assert response.status_code == 200

        data = response.json()
        assert "sql" in data
        assert "results" in data
        assert "chart_data" in data

    @patch("main.process_question", side_effect=_mock_process_question_count)
    def test_query_response_schema(self, mock_pq):
        """Response contains correctly structured chart_data."""
        response = client.post(
            "/query",
            json={"question": "What is the total number of customers?"},
        )
        assert response.status_code == 200

        data = response.json()
        chart_data = data["chart_data"]
        assert "labels" in chart_data
        assert "values" in chart_data
        assert isinstance(chart_data["labels"], list)
        assert isinstance(chart_data["values"], list)

    @patch("main.process_question", side_effect=_mock_process_question_count)
    def test_query_returns_results(self, mock_pq):
        """Results array is not empty for a valid question."""
        response = client.post(
            "/query",
            json={"question": "What is the total number of customers?"},
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data["results"]) > 0
        # The database has 500 customers
        first_result = data["results"][0]
        values = list(first_result.values())
        assert 500 in values

    @patch("main.process_question", side_effect=_mock_process_question_unanswerable)
    def test_invalid_question_returns_400(self, mock_pq):
        """Unanswerable questions return 400 with error detail."""
        response = client.post(
            "/query",
            json={"question": "What is the weather like today?"},
        )
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data


class TestMCPServer:
    """Tests for the MCP server tools directly."""

    def test_execute_query_rejects_drop(self):
        """execute_query rejects DROP TABLE statements."""
        with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
            execute_query("DROP TABLE customers")

    def test_execute_query_rejects_delete(self):
        """execute_query rejects DELETE statements."""
        with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
            execute_query("DELETE FROM customers WHERE id = 1")

    def test_execute_query_rejects_insert(self):
        """execute_query rejects INSERT statements."""
        with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
            execute_query("INSERT INTO customers (name, region, segment) VALUES ('test', 'North', 'Consumer')")

    def test_execute_query_rejects_update(self):
        """execute_query rejects UPDATE statements."""
        with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
            execute_query("UPDATE customers SET name = 'hacked' WHERE id = 1")

    def test_execute_query_allows_select(self):
        """execute_query allows valid SELECT queries."""
        results = execute_query("SELECT COUNT(*) AS cnt FROM customers")
        assert len(results) == 1
        assert results[0]["cnt"] == 500


class TestHealthEndpoint:
    """Tests for the GET / health endpoint."""

    def test_root_returns_200(self):
        """GET / returns 200 with service info."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "running"
