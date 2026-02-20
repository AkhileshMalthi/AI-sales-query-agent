"""
MCP Server for the Sales Database.

Uses the FastMCP framework from the official MCP SDK and SQLAlchemy
to expose secure, read-only tools for AI agents to interact with the SQLite database.
"""

import os

from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

# Initialize the FastMCP server
mcp = FastMCP("Sales Database MCP Server")

# Database URL configuration
# Default to the path used in the Docker container
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/sales.db")

# Initialize the SQLAlchemy engine
# We use a single engine instance for the application lifecycle
engine = create_engine(DATABASE_URL)


@mcp.tool()
def list_tables() -> list[str]:
    """Returns a list of all table names in the sales database."""
    inspector = inspect(engine)
    return inspector.get_table_names()


@mcp.tool()
def describe_schema(table_name: str) -> list[dict]:
    """Returns the schema (column names and types) for a given table.

    Args:
        table_name: The name of the table to describe.

    Returns:
        A list of dictionaries, each containing 'column_name' and 'column_type'.
    """
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        raise ValueError(f"Table '{table_name}' does not exist in the database.")

    columns = inspector.get_columns(table_name)
    return [
        {
            "column_name": col["name"],
            "column_type": str(col["type"]),
            "not_null": not col["nullable"],
            "primary_key": bool(col["primary_key"]),
        }
        for col in columns
    ]


@mcp.tool()
def execute_query(sql: str) -> list[dict]:
    """Executes a read-only SQL query against the sales database.

    Only SELECT statements are allowed. Any non-SELECT statement
    (INSERT, UPDATE, DELETE, DROP, ALTER, etc.) will be rejected.

    Args:
        sql: A SQL SELECT query to execute.

    Returns:
        A list of dictionaries, where each dictionary is a row from the result set.

    Raises:
        ValueError: If the query is not a SELECT statement or contains dangerous keywords.
    """
    # Strip and normalize the SQL
    cleaned_sql = sql.strip().rstrip(";").strip()

    # Reject non-SELECT statements
    if not cleaned_sql.upper().startswith("SELECT"):
        raise ValueError(
            f"Only SELECT queries are allowed. Received a query starting with: "
            f"'{cleaned_sql.split()[0] if cleaned_sql else '(empty)'}'"
        )

    # Additional safety: reject dangerous keywords even within SELECT
    dangerous_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "EXEC", "EXECUTE"]
    sql_upper = cleaned_sql.upper()
    for keyword in dangerous_keywords:
        # Check for these keywords as standalone words
        if f" {keyword} " in f" {sql_upper} ":
            raise ValueError(f"Query contains forbidden keyword: {keyword}")

    try:
        with engine.connect() as conn:
            # Defense-in-depth: enforce read-only at the connection level
            conn.execute(text("PRAGMA query_only = ON"))
            
            # Execute the query
            result = conn.execute(text(cleaned_sql))
            
            # Convert result to list of dicts
            return [dict(row._mapping) for row in result]
    except SQLAlchemyError as e:
        raise ValueError(f"SQL execution error: {e}") from e


# Allow running the MCP server standalone for testing
if __name__ == "__main__":
    mcp.run()
