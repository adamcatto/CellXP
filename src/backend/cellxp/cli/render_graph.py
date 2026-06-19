from pathlib import Path
from cellxp.agent.graph import app

def main():
    out_dir = Path("documentation/diagrams")
    out_dir.mkdir(parents=True, exist_ok=True)
    mermaid = app.get_graph(xray=True).draw_mermaid()
    (out_dir / "cellxp_graph.mmd").write_text(mermaid)
    try:
        png = app.get_graph(xray=True).draw_mermaid_png()
        (out_dir / "cellxp_graph.png").write_bytes(png)
    except Exception as exc:
        print(f"PNG rendering skipped: {exc}")

if __name__ == "__main__":
    main()
