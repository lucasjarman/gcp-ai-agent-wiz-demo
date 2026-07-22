import json
import sqlite3
from unittest.mock import patch

from langchain_core.messages import AIMessage, ToolMessage

from agent_service import AgentService, CUSTOMER_SCHEMA, SYSTEM_PROMPT


def database_factory():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE customers (id INTEGER, first_name TEXT, last_name TEXT, email TEXT, plan TEXT, monthly_spend REAL)"
    )
    connection.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "Sarah", "Mitchell", "sarah@example.test", "Enterprise", 4200.0),
            (2, "James", "Okonkwo", "james@example.test", "Professional", 890.0),
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


def test_sql_tool_returns_schema_help_for_invalid_column():
    service = AgentService(database_factory)
    sql_tool = next(item for item in service._build_tools() if item.name == "run_customer_sql")

    result = sql_tool.invoke(
        {"query": "SELECT plan, SUM(monthly_revenue) FROM customers GROUP BY plan"}
    )

    assert result.startswith("Query error:")
    assert "monthly_spend" in result
    assert "retry" in result.lower()


def test_sql_tool_ranks_plans_by_monthly_spend():
    service = AgentService(database_factory)
    sql_tool = next(item for item in service._build_tools() if item.name == "run_customer_sql")

    result = sql_tool.invoke(
        {
            "query": (
                "SELECT plan, SUM(monthly_spend) AS total_monthly_revenue "
                "FROM customers GROUP BY plan ORDER BY total_monthly_revenue DESC"
            )
        }
    )

    assert json.loads(result) == [
        {"plan": "Enterprise", "total_monthly_revenue": 4200.0},
        {"plan": "Professional", "total_monthly_revenue": 890.0},
    ]


def test_system_prompt_contains_exact_customer_schema():
    assert "monthly_spend REAL" in CUSTOMER_SCHEMA
    assert CUSTOMER_SCHEMA in SYSTEM_PROMPT
    assert "Do not invent column names" in SYSTEM_PROMPT


def test_agent_uses_configured_vertex_model(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    monkeypatch.setenv("VERTEX_LOCATION", "test-location")
    monkeypatch.setenv("VERTEX_MODEL", "test-model")
    service = AgentService(database_factory)

    with patch("agent_service.ChatVertexAI") as chat_vertex, patch(
        "agent_service.create_agent"
    ) as create_agent:
        service._get_agent()

    chat_vertex.assert_called_once_with(
        model_name="test-model",
        project="test-project",
        location="test-location",
        temperature=0.1,
    )
    assert create_agent.call_args.kwargs["model"] is chat_vertex.return_value


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
