# Monday.com Business Intelligence Agent

## Overview
AI agent that answers founder-level business questions by integrating live with Monday.com boards (Deals & Work Orders), cleaning messy data, and using a local AI model for unlimited, quota-free analysis.

## Features
- Live Monday.com API integration (no caching)
- Handles missing/nulls, normalizes formats
- Conversational interface (CLI)
- Local AI agent (Hugging Face Transformers)
- Visible API/tool-call trace
- Graceful error handling

## Setup
1. Install dependencies:
   pip install -r requirements.txt
   pip install transformers torch pandas requests
2. Set your Monday.com API token and board IDs in .env
3. Run the agent:
   python backend/bi_agent.py

## Tech Stack
- Python (FastAPI optional)
- Hugging Face Transformers (Mistral-7B-Instruct)
- pandas
- Monday.com GraphQL API

## Usage
- Import your CSVs as boards in Monday.com
- Ask business questions in the CLI
- See live API/tool-call trace for every query

## Deliverables
- Hosted prototype (local CLI, can be extended to web)
- Source code ZIP
- README & Decision Log
- Link to Monday.com boards

## Decision Log
See Decision_Log.md for architecture and tech choices.
3. Import all rows from the Excel files
4. Print the board IDs at the end

Copy the printed board IDs into your `.env` file:
```
MONDAY_DEALS_BOARD_ID=123456789
MONDAY_WORKORDERS_BOARD_ID=987654321
```

### Step 5: Run the Backend

```bash
cd monday-bi-agent/backend
python main.py
```

Server starts at: **http://localhost:8000**

### Step 6: Open the Chat UI

Open your browser to: **http://localhost:8000**

You'll see the Skylark Drones BI Agent chat interface.

---

## Usage Examples

Ask the agent questions like:

- *"How's our overall pipeline looking?"*
- *"What's the energy sector performance this quarter?"*
- *"Show me revenue and collection status"*
- *"Which deals are in the proposal stage?"*
- *"What's our accounts receivable?"*
- *"Mining sector deals by stage"*
- *"Top deals by value"*

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Chat UI |
| `/health` | GET | Config status check |
| `/chat` | POST | Send message, get AI response |

### Chat Request Format
```json
POST /chat
{
  "messages": [
    {"role": "user", "content": "How's our pipeline?"}
  ]
}
```

### Chat Response Format
```json
{
  "response": "Your pipeline has 346 active deals...",
  "tool_traces": [
    {
      "tool": "get_pipeline_health",
      "input": {},
      "status": "success",
      "output_summary": "Pipeline: 346 deals | WOs: 177 orders, 72.3% collected"
    }
  ]
}
```

---

## Monday.com Tools

The agent has 6 tools that make **live API calls**:

| Tool | Description |
|---|---|
| `get_pipeline_health` | Full overview of both boards |
| `get_deals_summary` | Filter deals by sector/status/stage |
| `get_work_orders_summary` | Filter WOs by sector/status |
| `get_sector_analysis` | Deep dive on a specific sector |
| `search_deals_by_keyword` | Keyword search across deals |
| `get_revenue_metrics` | Billing & collection breakdown |

---

## Hosting / Deployment

### Option A: Local (Development)
```bash
python backend/main.py
# Access at http://localhost:8000
```

### Option B: Railway / Render / Fly.io (Production)
1. Push code to GitHub
2. Connect repo to Railway/Render
3. Set environment variables in platform dashboard
4. Deploy — platform handles the rest

### Option C: Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ ./backend/
COPY frontend/ ./frontend/
EXPOSE 8000
CMD ["python", "backend/main.py"]
```

---

## Data Handling Notes

The data is intentionally messy. The agent handles:
- **Missing values** → skipped with caveat in response
- **Inconsistent date formats** → normalized via pandas
- **Empty sector/status fields** → labeled "Unknown" in aggregations
- **Masked financial data** → treated as-is (relative comparisons work)
- **Mixed number formats** → stripped of commas/₹ symbols before parsing

---

## Project Structure

```
monday-bi-agent/
├── backend/
│   ├── main.py          # FastAPI app + Claude agent + Monday.com tools
│   └── requirements.txt
├── frontend/
│   └── index.html       # Chat UI (single file)
├── scripts/
│   └── import_to_monday.py  # One-time data import script
├── data/
│   ├── Deal_funnel_Data.xlsx
│   └── Work_Order_Tracker_Data.xlsx
├── .env.example
└── README.md
```
