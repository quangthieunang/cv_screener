"""Node 1: boc Tool 1 (extract_cv_info) -> ghi cv_data vao state.

Truyen jd xuong tool de bat TIEN LOC TU KHOA: ho so khong nhac den ky nang bat
buoc nao se bi chan truoc khi ton mot lan goi LLM (tat qua jd["prefilter"]["enabled"]).
"""
import os
import sys

_CURRENT = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_CURRENT)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from state import CandidateState
from tools.extract_cv import extract_cv_info


def extract_node(state: CandidateState) -> dict:
    """Doc PDF -> cv_data. Neu loi, ghi vao errors va danh dau extraction_ok=False."""
    pdf_path = state["pdf_path"]
    errors = state.get("errors", [])

    cv_data = extract_cv_info(pdf_path, jd=state.get("jd"))

    if "error" in cv_data:
        # Loi doc/parse -> tao cv_data toi thieu de decide_node dua vao manual_review.
        return {
            "cv_data": {
                "name": "", "email": "", "phone": "",
                "skills": [], "years_experience": 0.0, "education": [],
                "extraction_ok": False, "note": cv_data["error"],
            },
            "errors": errors + [f"extract_node: {cv_data['error']}"],
        }

    return {"cv_data": cv_data}
