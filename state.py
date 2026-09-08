"""
Trang thai (state) cho LangGraph agent loc CV.

Moi lan chay graph xu ly MOT ung vien.
Batch nhieu CV do main.py lap va goi graph nhieu lan.
"""
from typing import TypedDict, Optional, List, Dict, Any


class CandidateState(TypedDict):
    """
    Trang thai cua mot ung vien khi di qua pipeline extract -> score -> decide.

    Cac truong:
    - pdf_path: Duong dan file PDF CV dang xu ly.
    - jd: Mo ta cong viec (job description) da nap tu jd.json (tieu chi + trong so + nguong).
    - cv_data: Output Tool 1 (extract_cv_info) - thong tin bóc tách tu CV.
    - score_result: Output Tool 2 (score_candidate) - diem + breakdown + ly do.
    - decision: "invite" | "reject" | "hold" | "manual_review".
    - email_result: Output Tool 3 (send_hr_email) - nhap hoac trang thai gui.
    - errors: Danh sach loi tich luy trong qua trinh chay.

    JSON contracts (giao keo giua cac node) - PHAI khop dung field ma node doc/ghi:

    1. cv_data  (Tool 1/extract_node -> Tool 2/score_node):
    {
        "name": "Nguyen Van A",
        "email": "a@example.com",
        "phone": "09xxxxxxxx",
        "skills": ["python", "sql", "docker"],   # da lowercase
        "years_experience": 3.5,                    # so (float), 0 neu khong ro
        "education": [
            {"degree": "bachelor", "field": "CNTT", "school": "..."}
        ],                                          # degree thuoc {highschool,college,bachelor,master,phd}
        "extraction_ok": true,                      # false neu PDF khong co lop text (CV scan anh)
        "prefilter_passed": true,                   # false neu bi tien loc tu khoa chan
                                                    # (khi do skills/years/education rong vi
                                                    #  ta CHU DONG bo qua LLM, khong phai ung
                                                    #  vien thuc su thieu)
        "name_guessed": false                       # true = ten do heuristic doan tu dong dau
                                                    #  CV (ho so bi tien loc chan, chua qua LLM).
                                                    #  decide_node doc co nay va KHONG dung ten
                                                    #  do de xung ho trong email gui ra ngoai.
    }

    2. score_result  (Tool 2/score_node -> decide_node):
    {
        "score": 82,                                # int 1-100
        "hard_filter_passed": true,
        "hard_filter_failures": [],                 # cac tieu chi bat buoc khong dat
        "breakdown": {"skills": 34, "experience": 27, "education": 15, "fit": 6},
        "matched_skills": ["python", "sql"],
        "missing_skills": ["kubernetes"],
        "reasons": ["...", "..."]
    }

    3. email_result  (Tool 3/decide_node):
    {
        "action": "invite" | "reject",
        "recipient": "a@example.com",
        "subject": "...",
        "body": "...",
        "status": "draft" | "sent" | "skipped" | "error",
        "path": "data/outputs/emails/invite_....txt"  # khi la draft
    }
    """
    pdf_path: str
    jd: Dict[str, Any]
    cv_data: Optional[Dict[str, Any]]
    score_result: Optional[Dict[str, Any]]
    decision: Optional[str]
    email_result: Optional[Dict[str, Any]]
    errors: List[str]
