"""
Cache ket qua BOC TACH CV theo noi dung file - de chay lai batch khong ton LLM.

VI SAO CAN:
    Tien loc tu khoa (tools/prefilter.py) cat duoc phan lon ho so rac, nhung moi
    ho so DAT tieu chi van ton mot lan goi LLM boc tach - va lan goi do lap lai
    y nguyen moi khi chay lai batch (doi trong so, doi nguong, thu JD khac...).
    Noi dung PDF khong doi thi ket qua boc tach cung khong doi -> cache duoc.

KHOA CACHE = sha256(LOP TEXT trich tu PDF, da cat theo do dai gui LLM) + ten model.
    - Bam LOP TEXT chu khong bam byte cua file: byte cua PDF chua ca metadata thoi
      diem tao, nen cung mot CV xuat lai tu Word se ra byte khac va truot cache du
      noi dung y nguyen. Lop text moi la thu QUYET DINH output cua LLM -> bam dung
      no la vua du va khong bao gio sai.
    - Theo NOI DUNG, khong theo duong dan: ung vien nop lai cung CV voi ten file
      khac van dung chung mot ban ghi.
    - Co ten model vi doi model la doi ket qua boc tach -> phai coi la cache khac.
    - KHONG dua JD vao khoa: boc tach khong phu thuoc JD (tien loc chay TRUOC cache
      nen viec JD nao chan ho so nao van dung).

DINH DANG = JSONL append-only (data/cache/extract_cache.jsonl).
    Ghi them mot dong moi lan cache mot ho so -> O(1)/ho so, khong phai ghi lai ca
    file (voi 500 CV, ghi lai ca file moi lan se la O(n^2)). Dong sau ghi de dong
    truoc cung khoa. File loi/dong hong duoc bo qua, khong lam vo pipeline.

CHI CACHE ket qua boc tach THANH CONG. Khong cache loi, khong cache ho so bi tien loc.

Bat/tat trong jd.json:
    {"cache": {"enabled": false}}                  # tat han
    {"cache": {"path": "/tmp/abc.jsonl"}}          # doi cho luu (dung trong test/benchmark)

Chay truc tiep de smoke test:
    python cache.py
"""
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

_CURRENT = os.path.dirname(os.path.abspath(__file__))
if _CURRENT not in sys.path:
    sys.path.insert(0, _CURRENT)

from config import EXTRACT_CACHE_PATH, MODEL_NAME

def text_fingerprint(text: str) -> str:
    """sha256 cua lop text CV - khoa cache.

    Gom khoang trang truoc khi bam de khac biet vo nghia (PDF hay doi cach xuong dong
    giua cac lan xuat file) khong lam truot cache.
    """
    normalized = " ".join((text or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class ExtractCache:
    """Cache boc tach CV, luu duoi dang JSONL append-only.

    Thuoc tinh dem (de benchmark/bao cao):
        hits    - so lan lay duoc tu cache (tiet kiem duoc 1 lan goi LLM)
        misses  - so lan tra cuu khong thay
        writes  - so ban ghi moi da ghi
    """

    def __init__(self, path=None, enabled: bool = True, model: str = None):
        self.path = Path(path) if path else Path(EXTRACT_CACHE_PATH)
        self.enabled = bool(enabled)
        self.model = model or MODEL_NAME
        self.hits = self.misses = self.writes = 0
        self._store = {}
        if self.enabled:
            self._load()

    # ── noi bo ──

    def _key(self, fingerprint: str) -> str:
        return f"{self.model}:{fingerprint}"

    def _load(self):
        """Nap toan bo file JSONL. Dong hong -> bo qua (cache khong bao gio lam vo pipeline)."""
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    key, cv = rec.get("key"), rec.get("cv_data")
                    if key and isinstance(cv, dict):
                        self._store[key] = cv     # dong sau ghi de dong truoc
        except OSError:
            pass

    # ── giao dien ──

    def get(self, fingerprint: str):
        """Tra ve BAN COPY cv_data da cache, hoac None."""
        if not self.enabled:
            return None
        cv = self._store.get(self._key(fingerprint))
        if cv is None:
            self.misses += 1
            return None
        self.hits += 1
        return json.loads(json.dumps(cv))   # copy sau de nguoi goi sua thoai mai

    def put(self, fingerprint: str, cv_data: dict, source: str = ""):
        """Ghi them mot ban ghi. Loi ghi file khong duoc lam vo pipeline."""
        if not self.enabled or not isinstance(cv_data, dict) or "error" in cv_data:
            return
        key = self._key(fingerprint)
        self._store[key] = cv_data
        rec = {
            "key": key, "model": self.model, "fingerprint": fingerprint,
            "source": os.path.basename(source or ""),
            "at": datetime.now().isoformat(timespec="seconds"),
            "cv_data": cv_data,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.writes += 1
        except OSError as e:
            print(f"⚠️  Khong ghi duoc cache ({e}) - bo qua, pipeline van chay.", file=sys.stderr)

    def stats(self) -> dict:
        return {"enabled": self.enabled, "hits": self.hits,
                "misses": self.misses, "writes": self.writes,
                "entries": len(self._store), "path": str(self.path)}


# Mot instance cho moi duong dan cache -> cac node trong cung mot batch dung chung
# bo dem, va khong phai nap lai file JSONL cho tung CV.
_REGISTRY = {}


def cache_for(jd: dict) -> ExtractCache:
    """Lay ExtractCache theo cau hinh trong jd (khoa "cache")."""
    cfg = (jd or {}).get("cache") or {}
    enabled = cfg.get("enabled", True) is not False
    path = Path(cfg.get("path") or EXTRACT_CACHE_PATH)
    key = (str(path.resolve() if path.parent.exists() else path), enabled, MODEL_NAME)
    if key not in _REGISTRY:
        _REGISTRY[key] = ExtractCache(path=path, enabled=enabled)
    return _REGISTRY[key]


def reset_registry():
    """Xoa registry - dung trong test de moi test co cache sach."""
    _REGISTRY.clear()


if __name__ == "__main__":
    import tempfile
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        fp = text_fingerprint("TRAN THI B\nBackend Engineer\nPython, SQL")
        print(f"fingerprint: {fp[:16]}...")
        print("khoang trang khac nhau -> cung khoa: "
              f"{fp == text_fingerprint('TRAN THI B   Backend Engineer  Python, SQL')}")

        c1 = ExtractCache(path=Path(tmp) / "c.jsonl")
        print(f"lan dau get -> {c1.get(fp)}  (mong doi None)")
        c1.put(fp, {"name": "Tran Thi B", "skills": ["python"]}, source="cv.pdf")

        c2 = ExtractCache(path=Path(tmp) / "c.jsonl")   # nap lai tu dia
        print(f"sau khi ghi, doc lai tu file -> {c2.get(fp)}")
        print(f"khong cache loi: {c2.put(fp, {'error': 'x'}) or 'da bo qua'}")
        print(f"stats: {c2.stats()}")

        off = ExtractCache(path=Path(tmp) / "c.jsonl", enabled=False)
        print(f"khi tat cache -> {off.get(fp)}  (mong doi None)")
