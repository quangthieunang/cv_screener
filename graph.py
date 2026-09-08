"""
LangGraph StateGraph: dieu phoi pipeline loc CV cho MOT ung vien.

Graph flow:
  START -> extract_node
  extract_node --(extraction_ok=False: CV scan anh)--> decide_node  (-> manual_review)
               --(ok)---------------------------------> score_node
  score_node -> decide_node -> END

Batch nhieu CV do main.py lap va goi app.invoke() nhieu lan.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph.graph import StateGraph, END

from state import CandidateState
from nodes.extract_node import extract_node
from nodes.score_node import score_node
from nodes.decide_node import decide_node


def route_after_extract(state: CandidateState) -> str:
    """PDF khong co text (extraction_ok=False) -> bo qua cham diem, di thang decide."""
    cv_data = state.get("cv_data") or {}
    if not cv_data.get("extraction_ok", True):
        return "decide"
    return "score"


def build_graph():
    """Tao va tra ve compiled LangGraph StateGraph."""
    graph = StateGraph(CandidateState)

    graph.add_node("extract", extract_node)
    graph.add_node("score", score_node)
    graph.add_node("decide", decide_node)

    graph.set_entry_point("extract")

    graph.add_conditional_edges(
        "extract",
        route_after_extract,
        {"score": "score", "decide": "decide"},
    )
    graph.add_edge("score", "decide")
    graph.add_edge("decide", END)

    return graph.compile()


# Singleton compiled graph
app = build_graph()


def screen_cv(pdf_path: str, jd: dict) -> dict:
    """Tien ich: chay pipeline cho 1 CV, tra ve state cuoi cung."""
    initial_state = CandidateState(
        pdf_path=pdf_path,
        jd=jd,
        cv_data=None,
        score_result=None,
        decision=None,
        email_result=None,
        errors=[],
    )
    return app.invoke(initial_state)


if __name__ == "__main__":
    import json
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    from config import JD_PATH, CVS_DIR

    with open(JD_PATH, "r", encoding="utf-8") as f:
        jd = json.load(f)

    # Smoke test: chay 1 CV mau (uu tien CV strong neu co).
    sample = CVS_DIR / "cv_strong_tran_thi_b.pdf"
    if not sample.exists():
        pdfs = sorted(CVS_DIR.glob("*.pdf"))
        sample = pdfs[0] if pdfs else None

    if sample is None:
        print(f"Khong co PDF nao trong {CVS_DIR} de test.")
        sys.exit(0)

    print(f"=== Smoke test graph: {sample.name} ===")
    result = screen_cv(str(sample), jd)
    print(f"Ten:        {(result.get('cv_data') or {}).get('name')}")
    print(f"Diem:       {(result.get('score_result') or {}).get('score')}")
    print(f"Quyet dinh: {result.get('decision')}")
    print(f"Email:      {(result.get('email_result') or {}).get('status')} "
          f"-> {(result.get('email_result') or {}).get('path', '(khong)')}")
    if result.get("errors"):
        print(f"Errors:     {result['errors']}")
