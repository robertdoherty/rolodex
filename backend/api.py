"""FastAPI server wrapping existing Rolodex database functions."""

import sys
from pathlib import Path

# Ensure sibling imports work (config, models, database are in this directory)
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse

import database

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
