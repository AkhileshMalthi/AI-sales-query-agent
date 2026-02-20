"""
SQL Agent — core logic for translating natural language to SQL.

Uses the MCP server tools to gather schema context, constructs a prompt
for the LLM, generates SQL, executes it, and formats the response.
"""

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from agent.llm import get_llm
from mcp_server import describe_schema, execute_query, list_tables


# --- Structured Output Schema ---


class SQLResponse(BaseModel):
    """Structured output from the LLM for SQL generation."""

    is_answerable: bool = Field(description="Whether the question can be answered using the given database schema.")
    sql: str = Field(
        default="",
        description=(
            "A single valid SQLite SELECT statement that answers the question. Must be empty if is_answerable is False."
        ),
    )
    explanation: str = Field(
        default="",
        description="Brief explanation of why the question is unanswerable (only if is_answerable is False).",
    )


# System prompt for SQL generation
SYSTEM_PROMPT = """You are an expert SQL analyst. Your job is to translate natural language questions
into precise SQLite SQL queries based on the database schema provided below.

## Database Schema
{schema_context}

## How to Analyze the Schema
1. Study the table names and column names to understand what data is available.
2. Identify relationships by looking for columns that reference other tables (e.g., a column named `user_id` likely references an `id` column in a `users` table).
3. Identify junction/bridge tables — tables that exist primarily to link two other tables (they typically have two foreign key columns and few or no other data columns).
4. Understand which columns are numeric (for SUM, AVG, COUNT) vs text (for filtering, grouping).
5. Look for date/time columns for any time-based analysis.

## Rules
1. ONLY use tables and columns that exist in the schema above — never invent tables or columns.
2. Infer table relationships from column names (foreign keys) and use appropriate JOINs.
3. Use aliases for readability (e.g., COUNT(*) AS total_count).
4. Use ROUND() for decimal results to 2 decimal places.
5. For date filters in SQLite, use strftime() or BETWEEN with string comparison.
6. If a question asks for "top N", use ORDER BY ... DESC LIMIT N.
7. Prefer LEFT JOIN when looking for records that DON'T have matches (e.g., "items that were never...").
8. When computing totals that span a junction table, multiply price × quantity at the line-item level.
9. If the question CANNOT be answered using the given schema, set is_answerable to False.

## Output Format
Respond with a JSON object containing:
- is_answerable: true/false
- sql: the SELECT query (empty string if unanswerable)
- explanation: why it's unanswerable (empty string if answerable)

## Examples (generic patterns)
Question: How many records are in a table?
Answer: {{"is_answerable": true, "sql": "SELECT COUNT(*) AS total_count FROM table_name", "explanation": ""}}

Question: Group and rank by count
Answer: {{"is_answerable": true, "sql": "SELECT t1.name, COUNT(t2.id) AS cnt FROM table1 t1 JOIN table2 t2 ON t1.id = t2.table1_id GROUP BY t1.id, t1.name ORDER BY cnt DESC", "explanation": ""}}

Question: What is the weather like?
Answer: {{"is_answerable": false, "sql": "", "explanation": "The database schema does not contain weather-related data."}}
"""


def _build_schema_context() -> str:
    """Build a human-readable schema context string from MCP server tools."""
    tables = list_tables()
    schema_parts = []

    for table in tables:
        columns = describe_schema(table)
        col_descriptions = []
        for col in columns:
            pk = " (PRIMARY KEY)" if col.get("primary_key") else ""
            nn = " NOT NULL" if col.get("not_null") else ""
            col_descriptions.append(f"    - {col['column_name']}: {col['column_type']}{pk}{nn}")

        schema_parts.append(f"### Table: {table}\n" + "\n".join(col_descriptions))

    return "\n\n".join(schema_parts)


def _build_chart_data(results: list[dict]) -> dict:
    """Extract chart-friendly data from query results.

    Uses the first string column as labels and the first numeric column as values.
    """
    if not results:
        return {"labels": [], "values": []}

    # Find the first string-like column and first numeric column
    first_row = results[0]
    label_key = None
    value_key = None

    for key, val in first_row.items():
        if label_key is None and isinstance(val, str):
            label_key = key
        if value_key is None and isinstance(val, (int, float)):
            value_key = key

    # If no string column found, use the first column as labels
    if label_key is None:
        keys = list(first_row.keys())
        label_key = keys[0]

    # If no numeric column found, use the second column or first
    if value_key is None:
        keys = list(first_row.keys())
        value_key = keys[1] if len(keys) > 1 else keys[0]

    labels = [str(row.get(label_key, "")) for row in results]
    values = []
    for row in results:
        v = row.get(value_key, 0)
        try:
            values.append(float(v))
        except (TypeError, ValueError):
            values.append(0.0)

    return {"labels": labels, "values": values}


def process_question(question: str) -> dict:
    """Process a natural language question and return SQL results.

    Args:
        question: The natural language question to answer.

    Returns:
        A dict with keys: sql, results, chart_data

    Raises:
        ValueError: If the question is unanswerable or the LLM generates invalid SQL.
        RuntimeError: If no LLM provider is available.
    """
    # 1. Build schema context from MCP tools
    schema_context = _build_schema_context()

    # 2. Create the LangChain prompt + LLM with structured output
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", "{question}"),
        ]
    )

    llm = get_llm()
    structured_llm = llm.with_structured_output(SQLResponse)
    chain = prompt | structured_llm

    # 3. Generate structured SQL response
    response: SQLResponse = chain.invoke(
        {
            "schema_context": schema_context,
            "question": question,
        }
    )

    # 4. Check if answerable
    if not response.is_answerable:
        available_tables = list_tables()
        reason = response.explanation or "The question cannot be answered with the available schema."
        raise ValueError(f"{reason} Available tables: {', '.join(available_tables)}.")

    # 5. Validate we got SQL
    sql = response.sql.strip().rstrip(";").strip()
    if not sql:
        raise ValueError("LLM returned an empty SQL query.")

    # 6. Execute the query via MCP server
    results = execute_query(sql)

    # 7. Build chart data
    chart_data = _build_chart_data(results)

    return {
        "sql": sql,
        "results": results,
        "chart_data": chart_data,
    }
