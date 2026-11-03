import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .build import build

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("DATA_DIR", ROOT / "data"))
STATIC = Path(__file__).resolve().parent / "static"

# last result lives here, small data so no database
state = {}


def load():
    state.update(build(DATA))
    return state["report"]


@asynccontextmanager
async def lifespan(app):
    load()
    yield


app = FastAPI(title="Event Sync Service", lifespan=lifespan)


@app.get("/api/meetings")
def meetings(
    where: str | None = Query(None, pattern="^(both|crm|cal)$"),
    conflict: bool | None = None,
    q: str | None = None,
):
    out = state["meetings"]
    if where:
        out = [m for m in out if m["where"] == where]
    if conflict is not None:
        out = [m for m in out if bool(m["conflicts"]) == conflict]
    if q:
        q = q.lower()
        # search title and client
        out = [m for m in out if q in (m["title"] or "").lower()
               or q in (m["fields"]["client"]["show"] or "").lower()]
    return {"count": len(out), "meetings": out}


@app.get("/api/meetings/{mid}")
def one_meeting(mid: str):
    for m in state["meetings"]:
        if m["id"] == mid.lower():
            return m
    raise HTTPException(404, "no meeting " + mid)


@app.get("/api/report")
def report():
    return state["report"]


@app.post("/api/sync")
def sync():
    # read the json files again
    return load()


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")
