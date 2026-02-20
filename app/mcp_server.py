"""
MCP Server for the Sales Database.

Uses the FastMCP framework from the official MCP SDK to expose secure,
read-only tools for AI agents to interact with the SQLite database.
"""

import os
import sqlite3

from mcp.server.fastmcp import FastMCP

# Initialize the FastMCP server
mcp = FastMCP("Sales Database MCP Server")

# Database path configuration
DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join("data", "sales.db"))


def _get_connection() -> sqlite3.Connection:
    """Create a read-only SQLite connection."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    # Defense-in-depth: enforce read-only at the database level
    conn.execute("PRAGMA query_only = ON")
    return conn


@mcp.tool()
def list_tables() -> list[str]:
    """Returns a list of all table names in the sales database."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        return tables
    finally:
        conn.close()


@mcp.tool()
def describe_schema(table_name: str) -> list[dict]:
    """Returns the schema (column names and types) for a given table.

    Args:
        table_name: The name of the table to describe.

    Returns:
        A list of dictionaries, each containing 'column_name' and 'column_type'.
    """
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        # Validate table name exists to prevent injection
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            raise ValueError(f"Table '{table_name}' does not exist in the database.")

        cursor.execute(f"PRAGMA table_info({table_name})")  # noqa: S608
        columns = [
            {
                "column_name": row[1],
                "column_type": row[2],
                "not_null": bool(row[3]),
                "primary_key": bool(row[5]),
            }
            for row in cursor.fetchall()
        ]
        return columns
    finally:
        conn.close()


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
        ValueError: If the query is not a SELECT statement.
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
        # Check for these keywords as standalone words (not part of column names)
        if f" {keyword} " in f" {sql_upper} ":
            raise ValueError(f"Query contains forbidden keyword: {keyword}")

    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(cleaned_sql)
        columns = [description[0] for description in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    except sqlite3.Error as e:
        raise ValueError(f"SQL execution error: {e}") from e
    finally:
        conn.close()


# Allow running the MCP server standalone for testing with MCP Inspector
if __name__ == "__main__":
    mcp.run()
