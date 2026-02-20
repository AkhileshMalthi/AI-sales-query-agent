"""
End-to-end integration tests for the AI Sales Query Agent.

These tests hit the REAL LLM (no mocking) and require:
  - A valid GROQ_API_KEY or ANTHROPIC_API_KEY in the environment
  - A seeded data/sales.db database

Run with:
    uv run pytest tests/ -m integration -v
"""

import os

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()

from main import app

# Skip entire module if no API key is available
pytestmark = pytest.mark.integration

HAS_API_KEY = bool(
    os.environ.get("GROQ_API_KEY", "").strip()
    or os.environ.get("ANTHROPIC_API_KEY", "").strip()
)

skip_no_key = pytest.mark.skipif(
    not HAS_API_KEY,
    reason="No LLM API key set (GROQ_API_KEY or ANTHROPIC_API_KEY required)",
)

client = TestClient(app)


# --- Evaluator Queries (same as evaluator.sh) ---

EVALUATOR_QUERIES = [
    "Top 3 customers by order count",
    "Average order value by region",
    "Monthly revenue for 2024",
    "Products that have never been ordered",
    "Total spend by customer segment",
]


@skip_no_key
class TestEndToEnd:
    """End-to-end tests that call the real LLM — NOT run in default CI."""

    @pytest.mark.parametrize("question", EVALUATOR_QUERIES)
    def test_evaluator_query_returns_results(self, question: str):
        """Each evaluator query should return 200 with non-empty results."""
        response = client.post(
            "/query",
            json={"question": question},
        )
        assert response.status_code == 200, f"Failed for: {question}"

        data = response.json()
        assert "sql" in data, "Response missing 'sql' key"
        assert "results" in data, "Response missing 'results' key"
        assert "chart_data" in data, "Response missing 'chart_data' key"
        assert len(data["results"]) > 0, f"Empty results for: {question}"

    def test_response_sql_is_select(self):
        """The generated SQL should always be a SELECT statement."""
        response = client.post(
            "/query",
            json={"question": "How many customers are there?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sql"].strip().upper().startswith("SELECT")

    def test_chart_data_structure(self):
        """chart_data should have labels and values as lists."""
        response = client.post(
            "/query",
            json={"question": "Total spend by customer segment"},
        )
        assert response.status_code == 200
        chart = response.json()["chart_data"]
        assert isinstance(chart["labels"], list)
        assert isinstance(chart["values"], list)
        assert len(chart["labels"]) > 0
        assert len(chart["values"]) > 0

    def test_unanswerable_question_returns_400(self):
        """An irrelevant question should return 400."""
        response = client.post(
            "/query",
            json={"question": "What is the weather like on Mars?"},
        )
        assert response.status_code == 400
        assert "detail" in response.json()
