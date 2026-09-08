"""Node 3: ra quyet dinh theo nguong + soan email nhap (Tool 3 dry-run).

Luu y: trong graph, decide_node LUON soan nhap (dry_run=True). Viec gui THAT chi
xay ra o main.py --send SAU khi nguoi dung xac nhan (tuan thu quy tac an toan).
"""
import os
import sys

_CURRENT = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_CURRENT)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from state import CandidateState
from tools.email_tool import send_hr_email
from config import INVITE_THRESHOLD, REJECT_THRESHOLD


def _decide(score_result: dict, cv_data: dict, jd: dict) -> str:
    """Quy tac quyet dinh -> 'invite' | 'hold' | 'reject' | 'manual_review'."""
    if not cv_data.get("extraction_ok", True):
        return "manual_review"
    if not score_result.get("hard_filter_passed", False):
        return "reject"

    thresholds = jd.get("thresholds") or {}
    invite_t = thresholds.get("invite", INVITE_THRESHOLD)
    reject_t = thresholds.get("reject", REJECT_THRESHOLD)

    score = score_result.get("score", 0)
    if score >= invite_t:
        return "invite"
    if score >= reject_t:
        return "hold"
    return "reject"


def decide_node(state: CandidateState) -> dict:
    """Quyet dinh + soan email nhap tuong ung (invite/reject). hold/manual_review khong soan."""
    cv_data = state.get("cv_data") or {}
    score_result = state.get("score_result") or {
        "score": 0, "hard_filter_passed": False,
    }
    jd = state.get("jd") or {}

    decision = _decide(score_result, cv_data, jd)

    # Chi invite/reject moi co email tu dong. hold & manual_review de HR xu ly tay.
    email_result = None
    if decision in ("invite", "reject"):
        # Ten do heuristic doan (ho so bi tien loc chan, chua qua LLM) thi KHONG dung
        # de xung ho: de trong -> mau email lui ve "anh/chi ung vien". Goi sai ten
        # mot nguoi la lo hong khong sua duoc sau khi email da gui.
        name = "" if cv_data.get("name_guessed") else cv_data.get("name", "")
        candidate = {
            "name": name,
            "email": cv_data.get("email", ""),
            "position": jd.get("position", ""),
            "ref": state.get("pdf_path", ""),   # de ten file ban nhap khong trung nhau
        }
        # dry_run=True: trong graph luon chi soan nhap, khong gui that.
        email_result = send_hr_email(
            candidate, decision, dry_run=True,
            out_dir=(jd.get("outputs") or {}).get("email_dir"),
        )
    else:
        email_result = {"action": decision, "status": "skipped",
                        "note": "Can HR xu ly tay (hold hoac review thu cong)."}

    return {"decision": decision, "email_result": email_result}
