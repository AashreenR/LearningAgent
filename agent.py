import json
import logging
import time
from typing import Any

from openai import OpenAI

import db
import tools as app_tools
from config import settings

logger = logging.getLogger(__name__)
MAX_ITERATIONS = 6

SYSTEM_PROMPT = """You are a friendly, practical AI learning coach.
Ask at most 1-2 short questions to learn the user's goal, current level, and
hours per week. When you have enough context, make a custom ordered plan with
5-10 achievable steps using free resources (official docs, freeCodeCamp,
YouTube, and similar). Use create_plan to save it. Only include URLs you are
confident exist; if unsure, use an empty URL. Keep replies concise.
If the user says they finished a step, use get_plans to identify it and
mark_step_done to mark it complete. Never claim a plan or step was saved unless
the corresponding tool succeeded. Tool errors are provided as tool results;
adapt and explain them clearly.
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "create_plan",
            "description": "Save a custom learning plan with 5-10 ordered steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "steps": {
                        "type": "array",
                        "minItems": 5,
                        "maxItems": 10,
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "url": {"type": "string"},
                            },
                            "required": ["title", "url"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["topic", "steps"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_plans",
            "description": "Get all saved learning plans and their steps.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_step_done",
            "description": "Mark a saved learning-plan step complete by its step ID.",
            "parameters": {
                "type": "object",
                "properties": {"step_id": {"type": "integer"}},
                "required": ["step_id"],
                "additionalProperties": False,
            },
        },
    },
]


def _client() -> OpenAI:
    if not settings.llm_api_key or not settings.llm_model:
        raise RuntimeError("Set LLM_API_KEY and LLM_MODEL in your .env file.")
    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def _run_tool(name: str, arguments: dict[str, Any]) -> Any:
    functions = {
        "create_plan": app_tools.create_plan,
        "get_plans": app_tools.get_plans,
        "mark_step_done": app_tools.mark_step_done,
    }
    function = functions.get(name)
    if function is None:
        raise ValueError(f"unknown tool: {name}")
    return function(**arguments)


def chat(session_id: str, message: str) -> str:
    client = _client()
    db.init_db()
    db.save_message(session_id, {"role": "user", "content": message})
    history = db.get_history(session_id)

    for _ in range(MAX_ITERATIONS):
        started = time.perf_counter()
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *history],
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        assistant_message = response.choices[0].message
        serialized = assistant_message.model_dump(exclude_none=True)
        tool_calls = assistant_message.tool_calls or []
        tool_names = [call.function.name for call in tool_calls]
        logger.info(
            "LLM call model=%s latency_ms=%d tool_calls=%s",
            settings.llm_model,
            elapsed_ms,
            tool_names,
        )

        if not tool_calls:
            reply = assistant_message.content or "I couldn't generate a reply. Please try again."
            db.save_message(session_id, serialized)
            return reply

        db.save_message(session_id, serialized)
        history.append(serialized)
        for call in tool_calls:
            try:
                arguments = json.loads(call.function.arguments)
                result = _run_tool(call.function.name, arguments)
                tool_result = {"ok": True, "result": result}
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                tool_result = {"ok": False, "error": str(error)}
            except Exception:
                logger.exception("Unexpected tool failure: %s", call.function.name)
                tool_result = {"ok": False, "error": "The tool failed unexpectedly."}
            tool_message = {
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(tool_result),
            }
            db.save_message(session_id, tool_message)
            history.append(tool_message)

    reply = "I reached the limit for this turn before I could finish. Please ask me to continue."
    db.save_message(session_id, {"role": "assistant", "content": reply})
    return reply
