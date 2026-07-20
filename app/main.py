import os
import sqlite3
import csv
import io
from typing import Literal

from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_service import AgentService

# SECURITY ISSUE: Hardcoded credentials — should be in Secret Manager
INTERNAL_API_KEY = "sk-ins-prod-9f2c8a4b1e7d3f6a"
DB_FALLBACK_URL = "postgresql://admin:P@ssw0rd123@db.internal:5432/customers"
ANALYTICS_TOKEN = "ghp_rK8mNxQvTw2pL9jYeZaFbUcDsHoI3n6q"
AWS_ACCESS_KEY_ID = "DEMO_AWS_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY = "DEMO_AWS_SECRET_ACCESS_KEY"

app = FastAPI(title="InsightHub API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

DB: sqlite3.Connection = None
AGENT_SERVICE: AgentService = None


class ChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=10)


def get_db():
    global DB
    if DB is None:
        DB = sqlite3.connect(":memory:", check_same_thread=False)
        DB.row_factory = sqlite3.Row
        _seed_database(DB)
    return DB


def get_agent_service():
    global AGENT_SERVICE
    if AGENT_SERVICE is None:
        AGENT_SERVICE = AgentService(get_db)
    return AGENT_SERVICE


def _seed_database(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            phone TEXT,
            ssn TEXT,
            credit_card TEXT,
            credit_card_expiry TEXT,
            plan TEXT,
            monthly_spend REAL,
            created_at TEXT
        )
    """)
    seed_data = [
        (1, "Sarah", "Mitchell", "sarah.mitchell@acmecorp.com", "+1-555-0142",
         "532-88-1947", "4532015112830366", "09/27", "Enterprise", 4200.00, "2022-03-14"),
        (2, "James", "Okonkwo", "james.okonkwo@vertextech.io", "+1-555-0289",
         "219-46-8833", "5425233430109903", "11/26", "Professional", 890.00, "2022-05-22"),
        (3, "Priya", "Ramachandran", "priya.r@globalfinance.com", "+1-555-0317",
         "784-21-6059", "4916338506082832", "04/28", "Enterprise", 7800.00, "2021-11-08"),
        (4, "Daniel", "Ferreira", "daniel.ferreira@bluepeak.net", "+1-555-0456",
         "631-74-2198", "374251018720018", "08/25", "Starter", 150.00, "2023-01-30"),
        (5, "Amanda", "Holloway", "a.holloway@nextgen-health.org", "+1-555-0521",
         "413-97-5526", "5105105105105100", "03/27", "Professional", 1200.00, "2022-08-15"),
        (6, "Michael", "Chen", "mchen@silicon-bridge.com", "+1-555-0634",
         "882-53-7741", "4111111111111111", "12/26", "Enterprise", 9400.00, "2021-06-03"),
        (7, "Fatima", "Al-Rashid", "fatima.alrashid@horizons-me.ae", "+971-55-7823",
         "N/A", "5500005555555559", "07/28", "Professional", 2100.00, "2022-12-19"),
        (8, "Robert", "Espinoza", "r.espinoza@cascadelogistics.com", "+1-555-0712",
         "276-84-3350", "4012888888881881", "02/26", "Starter", 75.00, "2023-04-07"),
        (9, "Yuki", "Tanaka", "y.tanaka@tokyoventures.jp", "+81-3-5555-1928",
         "N/A", "3566002020360505", "10/27", "Enterprise", 5600.00, "2022-02-28"),
        (10, "Chloe", "Beaumont", "c.beaumont@laviedesigns.fr", "+33-1-55-24-89-10",
         "N/A", "4716174954024855", "06/25", "Professional", 680.00, "2023-06-11"),
        (11, "Marcus", "Washington", "m.washington@fedstaff.gov", "+1-555-0883",
         "594-12-8867", "4532779879690481", "01/28", "Enterprise", 3300.00, "2021-09-17"),
        (12, "Elena", "Volkova", "e.volkova@eastblock-tech.ru", "+7-495-555-2847",
         "N/A", "5425233430109903", "05/26", "Starter", 90.00, "2023-02-14"),
        (13, "David", "Osei", "dosei@panafricanauto.co.ke", "+254-20-555-3301",
         "N/A", "4916338506082832", "09/27", "Professional", 445.00, "2022-10-30"),
        (14, "Jessica", "Park", "jpark@koreanwave-media.kr", "+82-2-555-8812",
         "N/A", "4111111111111111", "11/28", "Enterprise", 6200.00, "2021-07-22"),
        (15, "Thomas", "Bergmann", "t.bergmann@rhine-industrial.de", "+49-69-555-4471",
         "N/A", "3714496353984731", "03/26", "Professional", 1800.00, "2022-04-05"),
    ]
    conn.executemany(
        "INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?,?,?)", seed_data
    )
    conn.commit()


@app.on_event("startup")
def startup():
    get_db()


@app.get("/", response_class=HTMLResponse)
def root():
    with open("static/index.html") as f:
        return f.read()


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        return await get_agent_service().chat(
            request.message,
            [item.model_dump() for item in request.history],
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Agent unavailable: {exc}") from exc


@app.get("/api/customers")
def list_customers(search: str = Query(default="")):
    db = get_db()
    if search:
        # SECURITY ISSUE: SQL injection via string interpolation
        query = f"SELECT * FROM customers WHERE first_name LIKE '%{search}%' OR last_name LIKE '%{search}%' OR email LIKE '%{search}%'"
    else:
        query = "SELECT * FROM customers LIMIT 50"
    rows = db.execute(query).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return dict(row)


@app.get("/api/export")
def export_customers(format: str = Query(default="csv")):
    # SECURITY ISSUE: No authentication on this endpoint.
    # The running service account has Storage Object Admin access to the data bucket,
    # so this endpoint can read raw PII data from GCS without any auth check.
    bucket_name = os.environ.get("DATA_BUCKET")
    if bucket_name:
        try:
            from google.cloud import storage as gcs
            client = gcs.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob("customers.csv")
            csv_data = blob.download_as_text()
            return StreamingResponse(
                io.StringIO(csv_data),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=customers.csv"},
            )
        except Exception:
            pass

    # Fallback: export from in-memory DB
    db = get_db()
    rows = db.execute("SELECT * FROM customers").fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([d[0] for d in db.execute("SELECT * FROM customers LIMIT 0").description])
    for row in rows:
        writer.writerow(list(row))
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=customers.csv"},
    )


@app.get("/api/stats")
def get_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    enterprise = db.execute("SELECT COUNT(*) FROM customers WHERE plan='Enterprise'").fetchone()[0]
    professional = db.execute("SELECT COUNT(*) FROM customers WHERE plan='Professional'").fetchone()[0]
    starter = db.execute("SELECT COUNT(*) FROM customers WHERE plan='Starter'").fetchone()[0]
    total_revenue = db.execute("SELECT SUM(monthly_spend) FROM customers").fetchone()[0] or 0
    return {
        "total_customers": total,
        "by_plan": {
            "enterprise": enterprise,
            "professional": professional,
            "starter": starter,
        },
        "monthly_revenue": round(total_revenue, 2),
    }
