# Decision Log – Monday.com BI Agent
### Skylark Drones AI Engineer Assignment | Candidate Submission

---

## 1. Tech Stack Decisions

### Backend: Python + FastAPI
**Why:** FastAPI's async support is ideal for a tool-calling agent that makes multiple concurrent Monday.com API calls. Its auto-generated OpenAPI docs also help with debugging. Lightweight compared to Django — no unnecessary overhead for an API-first service.

### AI: Claude claude-opus-4-6 (Anthropic) with Tool Use
**Why:** Native tool/function calling with clean `stop_reason: "tool_use"` makes the agentic loop easy to implement correctly. Claude's context window handles large Monday.com API responses well. The tool-calling paradigm is a better fit than prompt-stuffing data — the agent decides what to query based on the user's question.

**Alternative considered:** GPT-4 function calling. Chose Claude for superior instruction-following on ambiguous queries and cleaner multi-tool call handling in a single response.

### Monday.com: GraphQL API (not MCP)
**Why:** Direct GraphQL API gives full control over query structure and error handling. The `items_page` query with `limit` parameter avoids fetching 500 items when 20 suffice. MCP would add an extra dependency layer and more setup friction for the evaluator.

**No caching policy:** Every `/chat` request triggers fresh Monday.com API calls. This satisfies the "live data" requirement and ensures consistency.

### Frontend: Single HTML File
**Why:** Zero dependency, zero build step. The evaluator opens one file and it works. Adding React/Next.js would add complexity without user-facing benefit for a prototype of this scope.

---

## 2. Agent Design Decisions

### Tool Granularity
Defined 6 tools instead of 1 generic "query" tool:
- Forces the agent to be explicit about what data it needs
- Each tool handles its own normalization and filtering
- Tool traces are more meaningful ("get_sector_analysis(mining)" vs "query_monday()")

### Agentic Loop
Implemented a `while True` loop that continues calling tools until `stop_reason == "end_turn"`. This supports multi-step reasoning: e.g., "How does mining compare to energy?" → agent calls `get_sector_analysis("mining")` AND `get_sector_analysis("energy")` before synthesizing.

### System Prompt Design
The system prompt explicitly:
1. Instructs Claude to ALWAYS use tools (prevent hallucination from training data)
2. Defines the data quality handling strategy upfront
3. Specifies founder-friendly output style (lead with the number)
4. Lists known sectors to help disambiguation

---

## 3. Data Quality Handling

The Excel data has several quality issues:

| Issue | Handling |
|---|---|
| Missing dates (empty Close Date) | Skipped in import; noted as caveat |
| Missing closure probability | Labeled "Unknown" in aggregations |
| Inconsistent sector casing | `.lower()` comparison for filtering |
| Mixed number formats | Strip ₹, commas before `float()` cast |
| Work Orders header on row 2 | `pd.read_excel(header=1)` |
| Masked names (Naruto, Scooby-Doo) | Treated as-is — anonymized data |

When financial fields are missing/zero, the agent communicates this as a data caveat rather than treating 0 as accurate.

---

## 4. Assumptions Made

1. **Board structure:** Created boards matching Excel column structure. In production, would coordinate with the monday.com admin to map to existing board schemas.

2. **Pagination:** Used `limit: 200` for summary queries. For boards > 200 items, cursor-based pagination would be needed. Noted in code comments.

3. **Currency:** All amounts assumed to be in Indian Rupees (₹) based on company context.

4. **Fiscal quarters:** Not hardcoded — the agent interprets "this quarter" based on the current date context provided in conversation.

5. **Security:** API keys stored in `.env` file (excluded from ZIP via `.gitignore`). In production, use a secrets manager (AWS Secrets Manager, Vault, etc.).

---

## 5. Trade-offs

| Decision | Chosen | Trade-off |
|---|---|---|
| No caching | Live API calls every time | Slower responses, but always fresh data |
| Claude claude-opus-4-6 | Best quality | Higher cost vs Haiku |
| Single HTML file | Simple deployment | No component reuse for larger app |
| GraphQL over REST | Full control | More boilerplate than monday.com SDK |

---

*Built within 6-hour time limit. All live. No preloaded data.*
