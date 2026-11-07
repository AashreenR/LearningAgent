import db
import tools


def setup_database(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()


def test_plan_crud_and_step_completion(monkeypatch, tmp_path):
    setup_database(monkeypatch, tmp_path)
    steps = [{"title": f"Step {number}", "url": ""} for number in range(1, 6)]

    created = tools.create_plan("Backend basics", steps)
    plans = tools.get_plans()
    assert created["id"] == plans[0]["id"]
    assert plans[0]["topic"] == "Backend basics"
    assert len(plans[0]["steps"]) == 5
    assert plans[0]["steps"][0]["position"] == 1
    assert plans[0]["steps"][0]["done"] is False

    updated = tools.mark_step_done(plans[0]["steps"][0]["id"])
    assert updated["done"] is True
    assert tools.get_plans()[0]["steps"][0]["done"] is True


def test_plan_tool_rejects_invalid_step_count(monkeypatch, tmp_path):
    setup_database(monkeypatch, tmp_path)

    try:
        tools.create_plan("Backend basics", [{"title": "Only step", "url": ""}])
    except ValueError as error:
        assert "between 5 and 10" in str(error)
    else:
        raise AssertionError("Expected invalid step count to be rejected")
    assert db.get_plans() == []
