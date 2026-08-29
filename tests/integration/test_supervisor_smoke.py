from cellxp.agent.graph import app


def test_supervisor_smoke():
    out = app.invoke({"user_query": "smoke", "subtasks": [{"type":"report"}]})
    assert "final_report" in out
