"""
Chong trung ung vien trong mot dot tuyen.

VI SAO CAN:
    Ung vien thuong nop nhieu lan (sua CV, nop qua nhieu kenh). Neu khong gop,
    HR se thay cung mot nguoi vai lan trong bang xep hang, va te hon - agent co
    the gui HAI email cho cung mot dia chi (vd lan 1 tu choi, lan 2 moi phong van).

NGUYEN TAC:
    - Chi gop khi co bang chung MANH: trung email, hoac trung so dien thoai.
      Ho ten trung KHONG du de gop (ho ten Viet Nam trung nhau rat pho bien)
      -> chi canh bao "nghi ngo trung" de HR tu quyet.
    - KHONG xoa ban ghi nao. Ban co diem cao nhat trong nhom lam ban chinh
      (primary), cac ban con lai duoc danh dau duplicate_of=<file ban chinh>.
      HR van thay day du trong bao cao; chi buoc GUI EMAIL la bo qua ban trung.

Chay truc tiep de smoke test:
    python dedupe.py
"""
import re
import unicodedata


def normalize_email(email: str) -> str:
    """Chuan hoa email de so sanh: bo khoang trang, ha chu thuong."""
    return re.sub(r"\s+", "", (email or "")).lower()


def normalize_phone(phone: str) -> str:
    """Chi giu chu so, lay 9 so cuoi.

    9 so cuoi de '+84912345678', '0912345678' va '912345678' deu ve cung mot khoa.
    It hon 9 chu so -> coi nhu khong du tin cay, tra "".
    """
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 9 else ""


def normalize_name(name: str) -> str:
    """Bo dau tieng Viet, ha chu thuong, gom khoang trang.

    'Nguyễn Văn A' va 'nguyen van a' -> cung mot khoa.
    """
    text = unicodedata.normalize("NFD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("đ", "d").replace("Đ", "D")
    return re.sub(r"\s+", " ", text).strip().lower()


def _strong_keys(rec: dict) -> list:
    """Cac khoa du manh de khang dinh trung nguoi (email, so dien thoai)."""
    keys = []
    email = normalize_email(rec.get("email", ""))
    if email:
        keys.append(("email", email))
    phone = normalize_phone(rec.get("phone", ""))
    if phone:
        keys.append(("phone", phone))
    return keys


class _UnionFind:
    """Gop nhom bac cau: A trung B qua email, B trung C qua phone -> A,B,C mot nhom."""

    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def dedupe_candidates(candidates: list) -> dict:
    """Danh dau ban ghi trung trong danh sach ung vien (sua tai cho + tra thong ke).

    Moi ban ghi duoc them:
        - "duplicate_of": ten file cua ban chinh (None neu chinh no la ban chinh)
        - "duplicate_count": so ban trung trong nhom (chi gan cho ban chinh)

    Tra ve:
        {
          "groups":  [[rec_chinh, rec_trung, ...], ...],   # cac nhom trung THAT
          "suspects": [[rec, rec, ...], ...],              # nghi ngo (chi trung ten)
          "duplicates_marked": int,                        # so ban bi danh dau trung
        }
    """
    for rec in candidates:
        rec.setdefault("duplicate_of", None)

    n = len(candidates)
    uf = _UnionFind(n)

    # 1. Gop theo khoa manh (email / phone)
    seen = {}
    for i, rec in enumerate(candidates):
        for key in _strong_keys(rec):
            if key in seen:
                uf.union(seen[key], i)
            else:
                seen[key] = i

    clusters = {}
    for i in range(n):
        clusters.setdefault(uf.find(i), []).append(i)

    groups, marked = [], 0
    for members in clusters.values():
        if len(members) < 2:
            continue
        # Ban chinh = diem cao nhat; hoa thi lay file dung truoc cho on dinh.
        members.sort(key=lambda i: (-candidates[i].get("score", 0), candidates[i].get("file", "")))
        primary = candidates[members[0]]
        primary["duplicate_count"] = len(members) - 1
        for i in members[1:]:
            candidates[i]["duplicate_of"] = primary.get("file")
            marked += 1
        groups.append([candidates[i] for i in members])

    # 2. Nghi ngo trung: cung ho ten chuan hoa nhung KHONG cung nhom khoa manh.
    #    Khong tu gop - chi bao de HR kiem tra.
    by_name = {}
    for i, rec in enumerate(candidates):
        name = normalize_name(rec.get("name", ""))
        if name:
            by_name.setdefault(name, []).append(i)

    suspects = []
    for members in by_name.values():
        if len(members) < 2:
            continue
        if len({uf.find(i) for i in members}) > 1:   # chua duoc gop boi khoa manh
            suspects.append([candidates[i] for i in members])

    return {"groups": groups, "suspects": suspects, "duplicates_marked": marked}


if __name__ == "__main__":
    import json
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    demo = [
        {"file": "cv_a_v1.pdf", "name": "Trần Thị B", "email": "b@x.com", "phone": "0912345678", "score": 71},
        {"file": "cv_a_v2.pdf", "name": "Tran Thi B", "email": "B@X.COM",  "phone": "",           "score": 84},
        {"file": "cv_a_v3.pdf", "name": "T.T.B",      "email": "b2@x.com", "phone": "+84912345678", "score": 60},
        {"file": "cv_c.pdf",    "name": "Nguyen Van A", "email": "a1@x.com", "phone": "0900000001", "score": 55},
        {"file": "cv_d.pdf",    "name": "Nguyễn Văn A", "email": "a2@x.com", "phone": "0900000002", "score": 52},
    ]
    stats = dedupe_candidates(demo)
    print(f"Nhom trung that: {len(stats['groups'])} | Danh dau trung: {stats['duplicates_marked']}")
    print(f"Nghi ngo trung ten: {len(stats['suspects'])}")
    print(json.dumps(demo, ensure_ascii=False, indent=2))
