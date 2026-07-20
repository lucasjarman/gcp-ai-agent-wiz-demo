import sqlite3

from langchain_core.messages import AIMessage, ToolMessage

from agent_service import AgentService


def database_factory():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE customers (id INTEGER, first_name TEXT, last_name TEXT, email TEXT, monthly_spend REAL)"
    )
    connection.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
        [
            (1, "Sarah", "Mitchell", "sarah@example.test", 4200.0),
            (2, "James", "Okonkwo", "james@example.test", 890.0),
        ],
    )
    return connection


def test_sql_tool_rejects_writes():
    service = AgentService(database_factory)
    sql_tool = next(item for item in service._build_tools() if item.name == "run_customer_sql")

    result = sql_tool.invoke({"query": "DELETE FROM customers"})

    assert result == "Rejected: only SELECT statements are allowed."


def test_sql_tool_allows_one_trailing_semicolon():
    service = AgentService(database_factory)
    sql_tool = next(item for item in service._build_tools() if item.name == "run_customer_sql")

    result = sql_tool.invoke({"query": "SELECT COUNT(*) AS total FROM customers;"})

    assert result == '[{"total": 2}]'


def test_search_tool_caps_results():
    service = AgentService(database_factory)
    search_tool = next(item for item in service._build_tools() if item.name == "search_customers")

    result = search_tool.invoke({"search_term": "a", "max_results": 50})

    assert "Sarah" in result
    assert "James" in result


def test_trace_contains_tool_call_and_result():
    messages = [
        AIMessage(
            content="",
            tool_calls=[{"name": "search_customers", "args": {"search_term": "Sarah"}, "id": "1"}],
        ),
        ToolMessage(content='[{"first_name":"Sarah"}]', tool_call_id="1", name="search_customers"),
        AIMessage(content="Sarah is an enterprise customer."),
    ]

    result = AgentService._format_result(messages)

    assert result["answer"] == "Sarah is an enterprise customer."
    assert [event["type"] for event in result["trace"]] == ["tool_call", "tool_result"]
