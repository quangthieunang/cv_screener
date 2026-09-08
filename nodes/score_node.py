"""Node 2: boc Tool 2 (score_candidate) -> ghi score_result vao state."""
import os
import sys

_CURRENT = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_CURRENT)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from state import CandidateState
from tools.score import score_candidate


def score_node(state: CandidateState) -> dict:
    """Cham diem cv_data theo jd -> score_result."""
    errors = state.get("errors", [])
    cv_data = state.get("cv_data") or {}
    jd = state.get("jd") or {}

    score_result = score_candidate(cv_data, jd)

    if "error" in score_result:
        # Loi cham diem -> diem 0, khong qua loc cung, de decide_node tu choi an toan.
        return {
            "score_result": {
                "score": 0, "hard_filter_passed": False,
                "hard_filter_failures": [score_result["error"]],
                "breakdown": {}, "matched_skills": [], "missing_skills": [],
                "reasons": [score_result["error"]],
            },
            "errors": errors + [f"score_node: {score_result['error']}"],
        }

    return {"score_result": score_result}
