from typing import Any

import db


def create_plan(topic: str, steps: list[dict[str, str]]) -> dict[str, Any]:
    if not topic.strip():
        raise ValueError("topic must not be empty")
    if not 5 <= len(steps) <= 10:
        raise ValueError("a plan must contain between 5 and 10 steps")
    for step in steps:
        if not isinstance(step.get("title"), str) or not step["title"].strip():
            raise ValueError("every step must have a non-empty title")
        if not isinstance(step.get("url", ""), str):
            raise ValueError("step url must be a string")
    normalized_steps = [
        {"title": step["title"].strip(), "url": step.get("url", "").strip()}
        for step in steps
    ]
    return db.create_plan(topic.strip(), normalized_steps)


def get_plans() -> list[dict[str, Any]]:
    return db.get_plans()


def mark_step_done(step_id: int) -> dict[str, Any]:
    step = db.set_step_done(step_id, True)
    if step is None:
        raise ValueError(f"step {step_id} was not found")
    return step
