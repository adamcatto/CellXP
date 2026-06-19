from cellxp.agent.graph import app

if __name__ == "__main__":
    print(app.invoke({"user_query": "smoke test", "subtasks": [{"type": "report"}]}))
