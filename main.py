import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

import agent
import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)

INDEX_FILE = Path(__file__).with_name("index.html")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="AI Learning Coach", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    started = time.perf_counter()
    logger.info("HTTP request started method=%s path=%s", request.method, request.url.path)
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    logger.info(
        "HTTP request method=%s path=%s status=%d latency_ms=%d",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


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
        logger.exception("Chat request failed")
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
