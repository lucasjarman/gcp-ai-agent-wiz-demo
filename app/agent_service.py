import json
import os
import re
import sqlite3
from collections.abc import Callable

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_google_vertexai import ChatVertexAI

from executor import BoundedPythonExecutor


CUSTOMER_SCHEMA = """customers (
  id INTEGER,
  first_name TEXT,
  last_name TEXT,
  email TEXT,
  phone TEXT,
  ssn TEXT,
  credit_card TEXT,
  credit_card_expiry TEXT,
  plan TEXT COLLATE NOCASE,
  monthly_spend REAL,
  created_at TEXT
)"""


SYSTEM_PROMPT = f"""You are InsightHub Analyst, an autonomous customer intelligence agent.
You work only with the synthetic demonstration dataset provided by your tools.
Use tools when facts or calculations are required and explain which tools you used.
The customer SQL tool is read-only. Never attempt writes, cloud administration, credential
access, or activity outside the demonstration dataset. Keep answers concise and useful.

The exact customer database schema is:
{CUSTOMER_SCHEMA}

Do not invent column names. For monthly revenue calculations, aggregate monthly_spend.
If a tool returns a query error, use the available-column guidance to correct the query and retry.
"""


class AgentService:
    def __init__(self, database_factory: Callable):
        self.database_factory = database_factory
        self.executor = BoundedPythonExecutor()
        self._agent = None

    async def chat(self, message: str, history: list[dict]) -> dict:
        agent = self._get_agent()
        messages = []
        for item in history[-10:]:
            if item["role"] == "user":
                messages.append(HumanMessage(content=item["content"]))
            elif item["role"] == "assistant":
                messages.append(AIMessage(content=item["content"]))
        messages.append(HumanMessage(content=message))

        result = await agent.ainvoke({"messages": messages})
        return self._format_result(result["messages"])

    def _get_agent(self):
        if self._agent is not None:
            return self._agent

        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("VERTEX_LOCATION", "global")
        if not project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is not configured")

        self._agent = create_agent(
            model=ChatVertexAI(
                model_name=os.environ.get("VERTEX_MODEL", "gemini-2.5-flash"),
                project=project,
                location=location,
                temperature=0.1,
            ),
            tools=self._build_tools(),
            system_prompt=SYSTEM_PROMPT,
            name="insighthub-analyst",
        )
        return self._agent

    def _build_tools(self):
        database_factory = self.database_factory
        executor = self.executor

        @tool("search_customers")
        def search_customers(search_term: str, max_results: int = 10) -> str:
            """Search the synthetic customer dataset by name, email, or plan."""
            limit = max(1, min(max_results, 10))
            like_value = f"%{search_term}%"
            rows = database_factory().execute(
                """
                SELECT * FROM customers
                WHERE first_name LIKE ? OR last_name LIKE ? OR email LIKE ? OR plan LIKE ?
                LIMIT ?
                """,
                (like_value, like_value, like_value, like_value, limit),
            ).fetchall()
            return json.dumps([dict(row) for row in rows])

        @tool("run_customer_sql")
        def run_customer_sql(query: str) -> str:
            """Execute one read-only SELECT query against synthetic customer records.

            Columns are id, first_name, last_name, email, phone, ssn, credit_card,
            credit_card_expiry, plan, monthly_spend, and created_at.
            """
            normalized = re.sub(r"\s+", " ", query.strip())
            if normalized.endswith(";"):
                normalized = normalized[:-1].rstrip()
            if not re.match(r"(?is)^select\b", normalized):
                return "Rejected: only SELECT statements are allowed."
            if ";" in normalized or re.search(r"(?i)\b(attach|detach|pragma)\b", normalized):
                return "Rejected: multiple statements and database directives are not allowed."
            connection = database_factory()
            try:
                rows = connection.execute(normalized).fetchmany(25)
            except sqlite3.Error as exc:
                columns = [row[1] for row in connection.execute("PRAGMA table_info(customers)")]
                return (
                    f"Query error: {exc}. Available columns: {', '.join(columns)}. "
                    "Correct the query and retry."
                )
            return json.dumps([dict(row) for row in rows])

        @tool("run_python_analysis")
        def run_python_analysis(code: str, data: list[dict] | None = None) -> str:
            """Run Python analysis in a bounded child process."""
            return executor.run_python(code, data)

        return [search_customers, run_customer_sql, run_python_analysis]

    @staticmethod
    def _format_result(messages: list) -> dict:
        trace = []
        answer = "I could not produce a response."

        for message in messages:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    trace.append(
                        {
                            "type": "tool_call",
                            "name": call["name"],
                            "input": call.get("args", {}),
                        }
                    )
                if message.content and not message.tool_calls:
                    answer = AgentService._message_text(message.content)
            elif isinstance(message, ToolMessage):
                trace.append(
                    {
                        "type": "tool_result",
                        "name": message.name or "tool",
                        "output": AgentService._message_text(message.content)[:1200],
                    }
                )

        return {"answer": answer, "trace": trace}

    @staticmethod
    def _message_text(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )
        return str(content)
