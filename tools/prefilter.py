"""
Tien loc tu khoa (keyword prefilter) - chay TRUOC khi goi LLM boc tach.

VI SAO CAN:
    Loc cung o Tool 2 tiet kiem LLM cho buoc CHAM DIEM, nhung Tool 1 van goi LLM
    cho ca 500 CV - do moi la chi phi chinh. Neu text tho cua CV KHONG chua bat ky
    ky nang bat buoc nao (vd "python", "sql"), gan nhu chac chan ho so do khong
    thuoc vi tri dang tuyen -> loai ngay voi chi phi ~0, khong ton mot lan goi LLM.

NGUYEN TAC AN TOAN - CO Y LAM LONG:
    Bo sot mot CV rac (cho di tiep) chi ton them mot lan goi LLM.
    Chan nham mot CV tot la loi NGHIEM TRONG, khong the sua.
    Vi vay:
      - Chi loai khi khong tim thay DU MOT ky nang bat buoc nao (khong phai
        "thieu mot vai ky nang" - viec do de Tool 2 quyet dinh tren du lieu da boc tach).
      - So khop la substring khong phan biet hoa thuong. "sql" khop ca "mysql",
        "postgresql", "nosql" - deu la tin hieu dung huong, va sai so chi lam
        bo loc DE DAI hon, khong bao gio chat hon.
      - Text qua ngan (CV scan anh, PDF loi) -> luon cho qua, de buoc sau xu ly.

Bat/tat trong jd.json:
    {"prefilter": {"enabled": false}}          # tat han
    {"prefilter": {"min_text_len": 300}}       # doi nguong text toi thieu

Chay truc tiep de smoke test:
    python tools/prefilter.py
"""
import os
import re
import sys

_CURRENT = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_CURRENT)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

# Text ngan hon nguong nay -> khong du co so de ket luan -> cho qua.
DEFAULT_MIN_TEXT_LEN = 200

# Ten goi khac cua cung mot cong nghe. Chi them nhung cap THUC SU khac ten;
# tranh alias qua ngan (vd "py") vi de khop nham vao tu khac.
SKILL_ALIASES = {
    "postgresql": ["postgres", "psql"],
    "javascript": ["ecmascript"],
    "typescript": ["ts lang"],
    "kubernetes": ["k8s"],
    "nodejs": ["node.js", "node js"],
    "c#": ["csharp", "c sharp"],
    ".net": ["dotnet", "asp.net"],
    "golang": ["go lang"],
    "machine learning": ["hoc may"],
    "deep learning": ["hoc sau"],
    "sql server": ["mssql", "t-sql"],
    "ci/cd": ["cicd", "ci cd"],
}


def _normalize(text: str) -> str:
    """Ha chu thuong + gom moi khoang trang (ke ca xuong dong) ve mot dau cach."""
    return re.sub(r"\s+", " ", (text or "").lower())


def _terms_for(skill: str) -> list:
    """Ky nang + cac ten goi khac cua no (tat ca chu thuong)."""
    skill = str(skill).strip().lower()
    return [skill] + [a.lower() for a in SKILL_ALIASES.get(skill, [])]


def keyword_prefilter(text: str, jd: dict) -> dict:
    """Quyet dinh co nen goi LLM boc tach cho CV nay khong.

    Tra ve:
        {
          "passed": bool,        # True = cho di tiep (goi LLM boc tach)
          "hits": [...],         # cac ky nang bat buoc tim thay trong text tho
          "checked": [...],      # cac ky nang bat buoc da do
          "reason": str,         # giai thich (tieng Viet, dua thang vao bao cao)
        }
    """
    jd = jd or {}
    cfg = jd.get("prefilter") or {}

    checked = [str(s).strip().lower()
               for s in ((jd.get("mandatory") or {}).get("required_skills") or [])
               if str(s).strip()]

    def _ok(reason):
        return {"passed": True, "hits": [], "checked": checked, "reason": reason}

    if cfg.get("enabled") is False:
        return _ok("Tien loc da bi tat trong cau hinh")

    if not checked:
        return _ok("JD khong khai bao ky nang bat buoc - khong co gi de tien loc")

    min_len = int(cfg.get("min_text_len", DEFAULT_MIN_TEXT_LEN) or 0)
    norm = _normalize(text)
    if len(norm) < min_len:
        return _ok(f"Text CV qua ngan ({len(norm)} ky tu) - cho qua de buoc sau xu ly")

    hits = [skill for skill in checked
            if any(term in norm for term in _terms_for(skill))]

    if hits:
        return {
            "passed": True, "hits": hits, "checked": checked,
            "reason": f"Tim thay ky nang bat buoc trong CV: {', '.join(hits)}",
        }

    return {
        "passed": False, "hits": [], "checked": checked,
        "reason": ("Tien loc tu khoa: CV khong nhac den bat ky ky nang bat buoc nao "
                   f"({', '.join(checked)}) - loai ma khong can goi LLM"),
    }


if __name__ == "__main__":
    import json
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    from config import JD_PATH
    with open(JD_PATH, "r", encoding="utf-8") as f:
        jd = json.load(f)

    filler = " kinh nghiem lam viec du an cong ty trach nhiem ky nang" * 12
    cases = {
        "Backend (co python)": "Nguyen Van A - Backend Developer. Thanh thao Python, Django." + filler,
        "DBA (chi co postgres)": "Tran Thi B - Database Administrator. PostgreSQL, Oracle." + filler,
        "Marketing (khong lien quan)": "Le Van C - Marketing. Facebook Ads, Photoshop, SEO." + filler,
        "Text qua ngan": "Nguyen Van D",
    }
    for label, text in cases.items():
        r = keyword_prefilter(text, jd)
        mark = "PASS -> goi LLM" if r["passed"] else "LOAI  -> bo qua LLM"
        print(f"{mark} | {label}\n   {r['reason']}\n")
