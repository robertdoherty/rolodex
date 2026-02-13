"""FastAPI server wrapping existing Rolodex database functions."""

import json
import sys
from pathlib import Path

# Ensure sibling imports work (config, models, database are in this directory)
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

import anthropic
import database
from config import PersonType, Tag
from local_secrets import ANTHROPIC_API_KEY

app = FastAPI(title="Rolodex")

FRONTEND_PATH = Path(__file__).parent.parent / "frontend" / "index.html"


@app.on_event("startup")
def startup():
    database.init_db()


@app.get("/")
def serve_frontend():
    if not FRONTEND_PATH.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(FRONTEND_PATH, media_type="text/html")


@app.get("/api/persons")
def api_list_persons():
    persons = database.list_persons()
    results = []
    for p in persons:
        results.append({
            "name": p.name,
            "current_company": p.current_company,
            "type": p.type.value if p.type else "",
            "interaction_count": len(p.interaction_ids),
        })
    return results


@app.get("/api/persons/{name}")
def api_get_person(name: str):
    person = database.get_person(name)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    interactions = database.get_interactions(name)
    interaction_summaries = []
    for i in interactions:
        interaction_summaries.append({
            "id": i.id,
            "person_name": i.person_name,
            "date": i.date.isoformat(),
            "takeaways": i.takeaways,
            "tags": [t.value for t in i.tags],
        })

    data = person.to_dict()
    data["interaction_ids"] = person.interaction_ids
    data["connections"] = person.connections
    data["interactions"] = interaction_summaries
    return data


@app.get("/api/interactions/{interaction_id}")
def api_get_interaction(interaction_id: int):
    interaction = database.get_interaction(interaction_id)
    if not interaction:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return interaction.to_dict()


@app.get("/api/followups/{name}")
def api_get_followups(name: str):
    followups = database.get_open_followups(name)
    return [f.to_dict() for f in followups]


@app.get("/api/connections/{name}")
def api_get_connections(name: str):
    return database.get_connections(name)


@app.post("/api/followups/{followup_id}/complete")
def api_complete_followup(followup_id: int):
    followup = database.complete_followup(followup_id)
    if not followup:
        raise HTTPException(status_code=404, detail="Followup not found")
    return followup.to_dict()


@app.get("/api/search")
def api_search(q: str = ""):
    if not q.strip():
        return []
    return database.search_text(q)


@app.get("/api/stats")
def api_stats():
    persons = database.list_persons()
    tag_counts = database.aggregate_tags()

    total_interactions = sum(len(p.interaction_ids) for p in persons)

    type_counts = {}
    for p in persons:
        t = p.type.value if p.type else "untyped"
        type_counts[t] = type_counts.get(t, 0) + 1

    total_followups = 0
    for p in persons:
        followups = database.get_open_followups(p.name)
        total_followups += len(followups)

    return {
        "total_persons": len(persons),
        "total_interactions": total_interactions,
        "total_open_followups": total_followups,
        "type_counts": type_counts,
        "tag_counts": tag_counts,
    }


# ── Chat Endpoint ──

CHAT_SYSTEM_PROMPT = """\
You are a Rolodex analyst. You answer questions about people and interactions stored in this CRM system.

Data coverage: The system tracks people (customers, investors, competitors) with interaction transcripts, takeaways, tags (pricing/product/gtm/competitors/market), company info, and followups.

Response calibration:
- Simple factual questions: 1-2 sentence answer, no preamble
- Comparisons: Bullet points, 3-7 items
- Analysis/reports: Structured with key findings, supporting quotes (attributed to person + date), and data gaps

Rules:
1. Only use data from the Rolodex tools. Never fabricate quotes, people, or interactions.
2. Attribute every quote to a specific person and date.
3. State evidence base: "Based on N interactions with M people..."
4. If fewer than 3 data points support a finding, flag it as thin evidence.
5. If a segment is missing from the data, say so.
"""

CHAT_TOOLS = [
    {
        "name": "list_persons",
        "description": "List all people in the Rolodex with name, company, type, and interaction count. Optionally filter by type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type_filter": {
                    "type": "string",
                    "enum": ["customer", "investor", "competitor"],
                    "description": "Filter by person type",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_person",
        "description": "Get full details for a person: company, type, background, state of play, last delta, company info, connections.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Exact person name"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_interactions",
        "description": "Get all interactions for a person (date, takeaways, tags). Does NOT include transcripts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "person_name": {"type": "string", "description": "Exact person name"},
            },
            "required": ["person_name"],
        },
    },
    {
        "name": "get_interaction",
        "description": "Get a single interaction by ID including full transcript.",
        "input_schema": {
            "type": "object",
            "properties": {
                "interaction_id": {"type": "integer", "description": "Interaction ID"},
            },
            "required": ["interaction_id"],
        },
    },
    {
        "name": "search_text",
        "description": "Full-text search across transcripts and takeaways. Returns matching interactions with transcript quotes and matching takeaways.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_interactions",
        "description": "Search interactions with filters. Returns interactions (without transcripts).",
        "input_schema": {
            "type": "object",
            "properties": {
                "tag": {
                    "type": "string",
                    "enum": ["pricing", "product", "gtm", "competitors", "market"],
                    "description": "Filter by tag",
                },
                "type": {
                    "type": "string",
                    "enum": ["customer", "investor", "competitor"],
                    "description": "Filter by person type",
                },
                "company": {"type": "string", "description": "Filter by company name (partial match)"},
                "text": {"type": "string", "description": "Full-text search within interactions"},
                "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            },
            "required": [],
        },
    },
    {
        "name": "aggregate_tags",
        "description": "Get tag frequency distribution, optionally filtered by person type or company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["customer", "investor", "competitor"],
                    "description": "Filter by person type",
                },
                "company": {"type": "string", "description": "Filter by company name"},
            },
            "required": [],
        },
    },
    {
        "name": "get_open_followups",
        "description": "Get open followup items for a person.",
        "input_schema": {
            "type": "object",
            "properties": {
                "person_name": {"type": "string", "description": "Exact person name"},
            },
            "required": ["person_name"],
        },
    },
]


def _execute_tool(name: str, input: dict):
    """Execute a tool call against database.py and return JSON-serializable result."""
    if name == "list_persons":
        type_filter = None
        if input.get("type_filter"):
            type_filter = PersonType(input["type_filter"])
        persons = database.list_persons(type_filter)
        return [
            {
                "name": p.name,
                "current_company": p.current_company,
                "type": p.type.value if p.type else "",
                "interaction_count": len(p.interaction_ids),
            }
            for p in persons
        ]

    elif name == "get_person":
        person = database.get_person(input["name"])
        if not person:
            return {"error": f"Person '{input['name']}' not found"}
        data = person.to_dict()
        data["interaction_ids"] = person.interaction_ids
        data["connections"] = person.connections
        return data

    elif name == "get_interactions":
        interactions = database.get_interactions(input["person_name"])
        return [
            {
                "id": i.id,
                "person_name": i.person_name,
                "date": i.date.isoformat()[:10],
                "takeaways": i.takeaways,
                "tags": [t.value for t in i.tags],
            }
            for i in interactions
        ]

    elif name == "get_interaction":
        interaction = database.get_interaction(input["interaction_id"])
        if not interaction:
            return {"error": f"Interaction {input['interaction_id']} not found"}
        return interaction.to_dict()

    elif name == "search_text":
        return database.search_text(input["query"])

    elif name == "search_interactions":
        tag = Tag(input["tag"]) if input.get("tag") else None
        person_type = PersonType(input["type"]) if input.get("type") else None
        interactions = database.search_interactions(
            tag=tag,
            person_type=person_type,
            company=input.get("company"),
            text=input.get("text"),
            date_from=input.get("date_from"),
            date_to=input.get("date_to"),
        )
        return [
            {
                "id": i.id,
                "person_name": i.person_name,
                "date": i.date.isoformat()[:10],
                "takeaways": i.takeaways,
                "tags": [t.value for t in i.tags],
            }
            for i in interactions
        ]

    elif name == "aggregate_tags":
        person_type = PersonType(input["type"]) if input.get("type") else None
        return database.aggregate_tags(person_type=person_type, company=input.get("company"))

    elif name == "get_open_followups":
        followups = database.get_open_followups(input["person_name"])
        return [f.to_dict() for f in followups]

    return {"error": f"Unknown tool: {name}"}


@app.post("/api/chat")
async def api_chat(request: Request):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    body = await request.json()
    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages required")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    async def generate():
        api_messages = [{"role": m["role"], "content": m["content"]} for m in messages]

        # Agent loop: keep calling until we get a text response
        while True:
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                system=CHAT_SYSTEM_PROMPT,
                tools=CHAT_TOOLS,
                messages=api_messages,
            )

            # Check if there are tool uses in the response
            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if response.stop_reason == "end_turn" or not tool_uses:
                # Final text response — emit as SSE
                text_blocks = [b.text for b in response.content if b.type == "text"]
                full_text = "\n".join(text_blocks)
                if full_text:
                    # Send in small chunks for progressive rendering
                    chunk_size = 20
                    for i in range(0, len(full_text), chunk_size):
                        yield f"data: {json.dumps({'type': 'text_delta', 'text': full_text[i:i+chunk_size]})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return

            # Process tool calls
            # Append assistant message with tool use blocks
            api_messages.append({"role": "assistant", "content": response.content})

            # Execute each tool and build tool results
            tool_results = []
            for tool_use in tool_uses:
                result = _execute_tool(tool_use.name, tool_use.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result, default=str),
                })

            api_messages.append({"role": "user", "content": tool_results})

    return StreamingResponse(generate(), media_type="text/event-stream")
