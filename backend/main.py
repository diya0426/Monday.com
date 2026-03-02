
"""
Monday.com BI Agent - Backend API
FastAPI server with Monday.com live integration
"""

import os
import json
import httpx
from typing import Any, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
 # ...existing code...

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────
 # ...existing code...
MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN")
MONDAY_DEALS_BOARD_ID = os.getenv("MONDAY_DEALS_BOARD_ID")
MONDAY_WORKORDERS_BOARD_ID = os.getenv("MONDAY_WORKORDERS_BOARD_ID")
MONDAY_API_URL = "https://api.monday.com/v2"

 # ...existing code...

# ─── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(title="Monday.com BI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pydantic Models ─────────
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

class ChatResponse(BaseModel):
    response: str
    tool_traces: list[dict]

# ─── Monday.com API Client ────────────────────────────────────────────────────
async def monday_graphql(query: str, variables: dict = None) -> dict:
    """Execute a GraphQL query against Monday.com API."""
    headers = {
        "Authorization": MONDAY_API_TOKEN,
        "Content-Type": "application/json",
        "API-Version": "2024-01",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(MONDAY_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    if "errors" in data:
        raise Exception(f"Monday.com API error: {data['errors']}")
    return data.get("data", {})


# ─── Tool Implementations ──────────────────────────────────────────────────────

async def get_deals_summary(
    sector: Optional[str] = None,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = 50
) -> dict:
    """Fetch deals from Monday.com with optional filters."""
    query = """
    query ($boardId: ID!, $limit: Int!) {
        boards(ids: [$boardId]) {
            name
            items_page(limit: $limit) {
                cursor
                items {
                    id
                    name
                    column_values {
                        id
                        title
                        text
                        value
                    }
                }
            }
        }
    }
    """
    data = await monday_graphql(query, {
        "boardId": MONDAY_DEALS_BOARD_ID,
        "limit": limit
    })

    boards = data.get("boards", [])
    if not boards:
        return {"error": "Deals board not found", "items": []}

    items = boards[0]["items_page"]["items"]
    deals = []

    for item in items:
        deal = {"name": item["name"], "id": item["id"]}
        for cv in item["column_values"]:
            deal[cv["title"]] = cv["text"] or ""
        deals.append(deal)

    # Apply filters
    if sector:
        sector_lower = sector.lower()
        deals = [d for d in deals if sector_lower in d.get("Sector", "").lower()]
    if status:
        status_lower = status.lower()
        deals = [d for d in deals if status_lower in d.get("Deal Status", "").lower()]
    if stage:
        stage_lower = stage.lower()
        deals = [d for d in deals if stage_lower in d.get("Deal Stage", "").lower()]

    # Compute summary stats
    total_value = 0
    for d in deals:
        val_str = d.get("Deal Value (Masked)", "").replace(",", "").replace("₹", "").strip()
        try:
            total_value += float(val_str) if val_str else 0
        except:
            pass

    return {
        "total_deals": len(deals),
        "total_value": total_value,
        "deals": deals[:20],  # Cap response size
        "filters_applied": {"sector": sector, "status": status, "stage": stage}
    }


async def get_work_orders_summary(
    sector: Optional[str] = None,
    status: Optional[str] = None,
    wo_status: Optional[str] = None,
    limit: int = 50
) -> dict:
    """Fetch work orders from Monday.com with optional filters."""
    query = """
    query ($boardId: ID!, $limit: Int!) {
        boards(ids: [$boardId]) {
            name
            items_page(limit: $limit) {
                items {
                    id
                    name
                    column_values {
                        id
                        title
                        text
                        value
                    }
                }
            }
        }
    }
    """
    data = await monday_graphql(query, {
        "boardId": MONDAY_WORKORDERS_BOARD_ID,
        "limit": limit
    })

    boards = data.get("boards", [])
    if not boards:
        return {"error": "Work Orders board not found", "items": []}

    items = boards[0]["items_page"]["items"]
    work_orders = []

    for item in items:
        wo = {"name": item["name"], "id": item["id"]}
        for cv in item["column_values"]:
            wo[cv["title"]] = cv["text"] or ""
        work_orders.append(wo)

    # Apply filters
    if sector:
        sector_lower = sector.lower()
        work_orders = [w for w in work_orders if sector_lower in w.get("Sector", "").lower()]
    if status:
        status_lower = status.lower()
        work_orders = [w for w in work_orders if status_lower in w.get("Execution Status", "").lower()]
    if wo_status:
        wo_status_lower = wo_status.lower()
        work_orders = [w for w in work_orders if wo_status_lower in w.get("WO Status", "").lower()]

    # Compute financial summary
    total_billed = 0
    total_collected = 0
    total_receivable = 0
    total_value = 0

    for w in work_orders:
        for field, accumulator in [
            ("Amount Excl GST", "value"),
            ("Billed Value Excl GST", "billed"),
            ("Collected Amount", "collected"),
            ("Amount Receivable", "receivable"),
        ]:
            val_str = w.get(field, "").replace(",", "").replace("₹", "").strip()
            try:
                num = float(val_str) if val_str else 0
                if field == "Amount Excl GST":
                    total_value += num
                elif field == "Billed Value Excl GST":
                    total_billed += num
                elif field == "Collected Amount":
                    total_collected += num
                elif field == "Amount Receivable":
                    total_receivable += num
            except:
                pass

    return {
        "total_work_orders": len(work_orders),
        "financial_summary": {
            "total_contract_value": total_value,
            "total_billed": total_billed,
            "total_collected": total_collected,
            "total_receivable": total_receivable,
        },
        "work_orders": work_orders[:20],
        "filters_applied": {"sector": sector, "status": status, "wo_status": wo_status}
    }


async def get_pipeline_health() -> dict:
    """Get overall pipeline health metrics across both boards."""
    deals_data = await get_deals_summary(limit=200)
    wo_data = await get_work_orders_summary(limit=200)

    deals = deals_data.get("deals", [])
    wos = wo_data.get("work_orders", [])

    # Deal stage breakdown
    stage_counts = {}
    for d in deals:
        stage = d.get("Deal Stage", "Unknown").strip() or "Unknown"
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    # Sector breakdown for deals
    sector_counts = {}
    for d in deals:
        sector = d.get("Sector", "Unknown").strip() or "Unknown"
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    # WO execution status breakdown
    exec_status_counts = {}
    for w in wos:
        st = w.get("Execution Status", "Unknown").strip() or "Unknown"
        exec_status_counts[st] = exec_status_counts.get(st, 0) + 1

    # WO sector breakdown
    wo_sector_counts = {}
    for w in wos:
        sector = w.get("Sector", "Unknown").strip() or "Unknown"
        wo_sector_counts[sector] = wo_sector_counts.get(sector, 0) + 1

    fin = wo_data.get("financial_summary", {})
    collection_rate = 0
    if fin.get("total_billed", 0) > 0:
        collection_rate = (fin["total_collected"] / fin["total_billed"]) * 100

    return {
        "deals_pipeline": {
            "total_deals": deals_data["total_deals"],
            "total_pipeline_value": deals_data["total_value"],
            "by_stage": stage_counts,
            "by_sector": sector_counts,
        },
        "work_orders": {
            "total_work_orders": wo_data["total_work_orders"],
            "financial_summary": fin,
            "collection_rate_pct": round(collection_rate, 1),
            "by_execution_status": exec_status_counts,
            "by_sector": wo_sector_counts,
        }
    }


async def get_sector_analysis(sector: str) -> dict:
    """Deep dive into a specific sector across both boards."""
    deals_data = await get_deals_summary(sector=sector, limit=200)
    wo_data = await get_work_orders_summary(sector=sector, limit=200)

    deals = deals_data.get("deals", [])

    # Probability breakdown
    prob_counts = {}
    for d in deals:
        prob = d.get("Closure Probability", "Unknown").strip() or "Unknown"
        prob_counts[prob] = prob_counts.get(prob, 0) + 1

    # Stage breakdown
    stage_counts = {}
    for d in deals:
        stage = d.get("Deal Stage", "Unknown").strip() or "Unknown"
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    fin = wo_data.get("financial_summary", {})

    return {
        "sector": sector,
        "deals": {
            "count": deals_data["total_deals"],
            "total_value": deals_data["total_value"],
            "by_probability": prob_counts,
            "by_stage": stage_counts,
            "sample_deals": [d["name"] for d in deals[:10]],
        },
        "work_orders": {
            "count": wo_data["total_work_orders"],
            "financial": fin,
        }
    }


async def search_deals_by_keyword(keyword: str) -> dict:
    """Search for deals matching a keyword in name, sector, product, or stage."""
    all_deals = await get_deals_summary(limit=500)
    deals = all_deals.get("deals", [])
    kw = keyword.lower()

    matched = [
        d for d in deals
        if kw in d.get("name", "").lower()
        or kw in d.get("Sector", "").lower()
        or kw in d.get("Product", "").lower()
        or kw in d.get("Deal Stage", "").lower()
        or kw in d.get("Deal Status", "").lower()
    ]

    return {
        "keyword": keyword,
        "matches": len(matched),
        "deals": matched[:15]
    }


async def get_revenue_metrics(period: Optional[str] = None) -> dict:
    """Get revenue and collection metrics from work orders."""
    wo_data = await get_work_orders_summary(limit=500)
    wos = wo_data.get("work_orders", [])

    # Group by billing status
    billing_buckets = {}
    for w in wos:
        bs = w.get("Billing Status", "Unknown").strip() or "Unknown"
        billing_buckets[bs] = billing_buckets.get(bs, 0) + 1

    # Group by collection status
    collection_buckets = {}
    for w in wos:
        cs = w.get("Collection Status", "Unknown").strip() or "Unknown"
        collection_buckets[cs] = collection_buckets.get(cs, 0) + 1

    fin = wo_data.get("financial_summary", {})

    return {
        "financial_summary": fin,
        "billing_status_breakdown": billing_buckets,
        "collection_status_breakdown": collection_buckets,
        "total_work_orders": len(wos),
    }


 # ...existing code...

# ─── Tool Executor ─────────────────────────────────────────────────────────────
async def execute_tool(tool_name: str, tool_input: dict) -> Any:
    """Execute a tool call and return result."""
    if tool_name == "get_deals_summary":
        return await get_deals_summary(**tool_input)
    elif tool_name == "get_work_orders_summary":
        return await get_work_orders_summary(**tool_input)
    elif tool_name == "get_pipeline_health":
        return await get_pipeline_health()
    elif tool_name == "get_sector_analysis":
        return await get_sector_analysis(**tool_input)
    elif tool_name == "search_deals_by_keyword":
        return await search_deals_by_keyword(**tool_input)
    elif tool_name == "get_revenue_metrics":
        return await get_revenue_metrics(**tool_input)
    else:
        return {"error": f"Unknown tool: {tool_name}"}


 # ...existing code...
        return final_text, tool_traces

        # Execute all tool calls
        tool_response_parts = []
        for fn_call in fn_calls:
            tool_name = fn_call.name
            tool_input = dict(fn_call.args)

            trace = {"tool": tool_name, "input": tool_input, "status": "calling"}

            try:
                result = await execute_tool(tool_name, tool_input)
                trace["status"] = "success"
                trace["output_summary"] = _summarize_result(result)
                tool_response_parts.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=tool_name,
                            response={"result": result}
                        )
                    )
                )
            except Exception as e:
                trace["status"] = "error"
                trace["error"] = str(e)
                tool_response_parts.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=tool_name,
                            response={"error": str(e)}
                        )
                    )
                )

            tool_traces.append(trace)

        # Send tool results back to Gemini
        response = await chat.send_message_async(tool_response_parts)


def _summarize_result(result: dict) -> str:
    """Create a brief summary of tool result for the trace."""
    if "error" in result:
        return f"Error: {result['error']}"
    if "total_deals" in result:
        return f"{result['total_deals']} deals, total value ₹{result.get('total_value', 0):,.0f}"
    if "total_work_orders" in result:
        fin = result.get("financial_summary", {})
        return f"{result['total_work_orders']} WOs, billed ₹{fin.get('total_billed', 0):,.0f}"
    if "deals_pipeline" in result:
        dp = result["deals_pipeline"]
        wo = result["work_orders"]
        return f"Pipeline: {dp['total_deals']} deals | WOs: {wo['total_work_orders']} orders, {wo['collection_rate_pct']}% collected"
    if "sector" in result:
        return f"Sector '{result['sector']}': {result['deals']['count']} deals, {result['work_orders']['count']} WOs"
    if "matches" in result:
        return f"Found {result['matches']} matching deals"
    if "financial_summary" in result:
        fin = result["financial_summary"]
        return f"Billed ₹{fin.get('total_billed', 0):,.0f}, Collected ₹{fin.get('total_collected', 0):,.0f}"
    return "Data retrieved successfully"


# ─── API Routes ────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "monday_deals_board": MONDAY_DEALS_BOARD_ID,
        "monday_wo_board": MONDAY_WORKORDERS_BOARD_ID,
        # "gemini_configured": False,  # Gemini removed
        "monday_configured": bool(MONDAY_API_TOKEN),
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # Gemini removed: no GEMINI_API_KEY check
    if not MONDAY_API_TOKEN:
        raise HTTPException(500, "MONDAY_API_TOKEN not configured")
    if not MONDAY_DEALS_BOARD_ID or not MONDAY_WORKORDERS_BOARD_ID:
        raise HTTPException(500, "Monday.com board IDs not configured")

    messages = [m.dict() for m in request.messages]
    
    # Gemini agent removed. Replace with a placeholder or implement local agent logic here.
    return ChatResponse(response="Agent functionality not implemented in backend. Use local agent script (bi_agent.py)", tool_traces=[])


# ─── Serve Frontend ────────────────────────────────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
