from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

import agent
import db

INDEX_FILE = Path(__file__).with_name("index.html")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="AI Learning Coach", lifespan=lifespan)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=8000)


@app.get("/")
def home() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
def post_chat(request: ChatRequest) -> dict[str, str]:
    try:
        return {"reply": agent.chat(request.session_id, request.message)}
    except Exception as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/plans")
def plans() -> list[dict]:
    return db.get_plans()


@app.post("/steps/{step_id}/toggle")
def toggle_step(step_id: int) -> dict:
    step = db.toggle_step(step_id)
    if step is None:
        raise HTTPException(status_code=404, detail="Step not found")
    return step
