"""
Do hieu nang batch lon - hang muc 9 trong DESIGN.md.

VI SAO CAN:
    Toan bo thiet ke duoc bien minh bang mot con so: "500 CV, 80% khong dat, doc tay
    ton hang chuc gio". Neu khong do, ta khong biet agent that su nhanh hon bao nhieu,
    va khong biet tien loc + cache tiet kiem duoc bao nhieu lan goi LLM.

CACH DO:
    Sinh N ho so gia lap (moi ho so co noi dung KHAC nhau de cache khong gian lan),
    theo ty le rac dat truoc, roi chay dung pipeline that (graph.screen_cv) va do
    thoi gian tung ho so.

    --mock-llm  do phan TAT DINH (doc PDF + tien loc + cham diem Python) ma khong can
                Ollama. Dung de do thong luong tran va de chay tren CI.
    khong co co -> goi Ollama that: con so s/CV moi la con so dung de bao cao.

    --warm      chay them luot thu hai tren cung bo CV de do hieu qua CACHE.

Benchmark KHONG de lai rac: CV gia lap, cache va ban nhap email deu nam trong thu
muc tam va bi xoa khi ket thuc.

Vi du:
    python benchmark.py --n 500 --mock-llm            # thong luong tran, khong can Ollama
    python benchmark.py --n 25 --warm                 # so lieu that (Ollama), co do cache
    python benchmark.py --n 100 --junk-ratio 0.5      # doi ty le ho so rac
"""
import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import fitz

import cache as cache_mod
import tools.extract_cv as extract_mod
import tools.score as score_mod
from config import JD_PATH, MODEL_NAME
from graph import screen_cv

# ── Sinh ho so gia lap ──
# Moi ho so phai co noi dung KHAC nhau, neu khong cache se bao "hit" gia va con so
# tiet kiem thanh vo nghia.

_RELEVANT = """UNG VIEN SO {i}
Backend Engineer
Email: ungvien{i}@example.com
Phone: 09{i:08d}
Ky nang: Python, SQL, {extra}
Kinh nghiem: {years} nam phat trien REST API va toi uu truy van
Du an {i}: he thong dich vu web, xu ly {i}00 request moi giay
Hoc van: Cu nhan Cong nghe thong tin - Dai hoc So {i}
"""

_JUNK = """UNG VIEN SO {i}
Chuyen vien {role}
Email: ungvien{i}@example.com
Phone: 09{i:08d}
Ky nang: Facebook Ads, Photoshop, Illustrator, SEO, Content, Canva
Kinh nghiem: {years} nam chay quang cao va quan ly fanpage cho nhan hang so {i}
Du an {i}: chien dich truyen thong cho {i} thuong hieu ban le
Hoc van: Cu nhan {role} - Dai hoc So {i}
"""

_EXTRA = ["Docker, AWS", "FastAPI, Redis", "Docker, Kubernetes", "PostgreSQL, Celery"]
_ROLES = ["Marketing", "Nhan su", "Ke toan", "Hanh chinh", "Thiet ke do hoa"]


def _write_pdf(path, text):
    doc = fitz.open()
    page = doc.new_page()
    y = 60
    for line in text.splitlines():
        page.insert_text((55, y), line, fontsize=10)
        y += 14
    doc.save(str(path))
    doc.close()


def generate_cvs(out_dir, n, junk_ratio):
    """Sinh n file PDF vao out_dir. Tra ve so ho so RAC (du kien bi tien loc chan)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    n_junk = int(round(n * junk_ratio))
    for i in range(1, n + 1):
        if i <= n_junk:
            text = _JUNK.format(i=i, role=_ROLES[i % len(_ROLES)], years=1 + i % 6)
        else:
            text = _RELEVANT.format(i=i, extra=_EXTRA[i % len(_EXTRA)], years=2 + i % 8)
        _write_pdf(out_dir / f"cv_{i:04d}.pdf", text)
    return n_junk


# ── Dem so lan goi LLM ──

_MOCK_EXTRACT = {
    "name": "Ung Vien", "email": "", "phone": "",
    "skills": ["python", "sql", "docker"], "years_experience": 4,
    "education": [{"degree": "bachelor", "field": "CNTT", "school": "X"}],
}
_MOCK_FIT = {"fit_score": 0.7, "reasons": ["mock"]}


class LLMCounter:
    """Boc chat_json de dem so lan goi va thoi gian. mock khac None -> khong cham Ollama."""

    def __init__(self, real, mock_response=None):
        self._real = real
        self._mock = mock_response
        self.calls = 0
        self.seconds = 0.0

    def __call__(self, prompt, system_prompt="", schema_hint=""):
        self.calls += 1
        t0 = time.perf_counter()
        try:
            if self._mock is not None:
                return self._mock
            return self._real(prompt, system_prompt=system_prompt, schema_hint=schema_hint)
        finally:
            self.seconds += time.perf_counter() - t0


# Giu ham that de moi luot boc lai tu goc, khong boc long nhieu lop.
_REAL_EXTRACT_CHAT = extract_mod.chat_json
_REAL_SCORE_CHAT = score_mod.chat_json


def install_counters(mock):
    ex = LLMCounter(_REAL_EXTRACT_CHAT, _MOCK_EXTRACT if mock else None)
    fit = LLMCounter(_REAL_SCORE_CHAT, _MOCK_FIT if mock else None)
    extract_mod.chat_json = ex
    score_mod.chat_json = fit
    return ex, fit


# ── Chay mot luot ──

def run_pass(label, jd, pdfs, progress_every=25):
    per_cv, decisions, n_prefiltered = [], {}, 0
    t_start = time.perf_counter()

    for i, pdf in enumerate(pdfs, 1):
        t0 = time.perf_counter()
        result = screen_cv(str(pdf), jd)
        per_cv.append(time.perf_counter() - t0)

        dec = result.get("decision", "?")
        decisions[dec] = decisions.get(dec, 0) + 1
        if not (result.get("cv_data") or {}).get("prefilter_passed", True):
            n_prefiltered += 1

        if i % progress_every == 0 or i == len(pdfs):
            print(f"   {label}: {i}/{len(pdfs)} ho so "
                  f"({time.perf_counter() - t_start:.1f}s)", flush=True)

    total = time.perf_counter() - t_start
    ordered = sorted(per_cv)
    return {
        "label": label, "n": len(pdfs), "total": total,
        "mean": statistics.fmean(per_cv) if per_cv else 0.0,
        "median": statistics.median(per_cv) if per_cv else 0.0,
        "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] if ordered else 0.0,
        "max": max(per_cv) if per_cv else 0.0,
        "prefiltered": n_prefiltered, "decisions": decisions,
    }


def print_pass(r, ex, fit, cache):
    n, total = r["n"], r["total"]
    llm_calls = ex.calls + fit.calls
    llm_secs = ex.seconds + fit.seconds

    print(f"\n── {r['label']} ──")
    print(f"   Tong thoi gian     : {total:.1f}s cho {n} ho so")
    print(f"   Trung binh / CV    : {r['mean']:.2f}s   (median {r['median']:.2f}s, "
          f"p95 {r['p95']:.2f}s, max {r['max']:.2f}s)")
    if total > 0:
        print(f"   Thong luong        : {n / total:.1f} ho so/giay")
    print(f"   Tien loc chan      : {r['prefiltered']}/{n} "
          f"({r['prefiltered'] / n * 100:.0f}%) - khong ton lan goi LLM")
    print(f"   Cache lay lai      : {cache.hits} (ghi moi {cache.writes})")
    print(f"   So lan goi LLM     : {ex.calls} (boc tach) + {fit.calls} (cham fit) "
          f"= {llm_calls}")
    if total > 0:
        print(f"   Thoi gian trong LLM: {llm_secs:.1f}s ({llm_secs / total * 100:.0f}% tong)")
    print("   Quyet dinh         : "
          + ", ".join(f"{k}={v}" for k, v in sorted(r["decisions"].items())))

    # Khong co 3 lop tiet kiem thi moi ho so ton dung 1 lan goi boc tach.
    saved = n - ex.calls
    if saved > 0:
        print(f"   => Tiet kiem       : {saved}/{n} lan goi LLM boc tach "
              f"({saved / n * 100:.0f}%)")
    print(f"   => Du bao 500 CV   : {r['mean'] * 500 / 60:.1f} phut")


def main():
    ap = argparse.ArgumentParser(description="Do hieu nang batch lon cua cv-screener.")
    ap.add_argument("--n", type=int, default=100, help="So ho so gia lap (mac dinh 100)")
    ap.add_argument("--junk-ratio", type=float, default=0.8,
                    help="Ty le ho so khong lien quan (mac dinh 0.8 - mo phong tinh huong thuc te)")
    ap.add_argument("--mock-llm", action="store_true",
                    help="Khong goi Ollama - chi do phan tat dinh")
    ap.add_argument("--warm", action="store_true",
                    help="Chay them luot 2 tren cung bo CV de do hieu qua cache")
    ap.add_argument("--jd", type=str, default=str(JD_PATH))
    args = ap.parse_args()

    with open(args.jd, "r", encoding="utf-8") as f:
        jd = json.load(f)

    print("=" * 68)
    print(f"⏱️  BENCHMARK cv-screener - {args.n} ho so, "
          f"{args.junk_ratio:.0%} rac, LLM={'mock' if args.mock_llm else MODEL_NAME}")
    print("=" * 68)

    with tempfile.TemporaryDirectory(prefix="cv_bench_") as tmp:
        tmp = Path(tmp)
        cvs, out = tmp / "cvs", tmp / "out"

        print(f"\n📄 Sinh {args.n} ho so gia lap ...", flush=True)
        t0 = time.perf_counter()
        n_junk = generate_cvs(cvs, args.n, args.junk_ratio)
        print(f"   xong trong {time.perf_counter() - t0:.1f}s "
              f"({n_junk} rac / {args.n - n_junk} lien quan)")

        # Cache + ban nhap email deu trong thu muc tam -> khong de lai rac.
        jd.setdefault("cache", {})
        jd["cache"].update({"enabled": True, "path": str(tmp / "cache.jsonl")})
        jd.setdefault("outputs", {})["email_dir"] = str(out / "emails")
        cache_mod.reset_registry()

        pdfs = sorted(cvs.glob("*.pdf"))

        ex, fit = install_counters(args.mock_llm)
        r1 = run_pass("Luot 1 (cache lanh)", jd, pdfs)
        print_pass(r1, ex, fit, cache_mod.cache_for(jd))

        if args.warm:
            cache_mod.reset_registry()   # gia lap tien trinh moi: doc lai cache tu dia
            ex2, fit2 = install_counters(args.mock_llm)
            r2 = run_pass("Luot 2 (cache nong)", jd, pdfs)
            print_pass(r2, ex2, fit2, cache_mod.cache_for(jd))
            if r2["total"] > 0:
                print(f"\n   💾 Cache lam luot 2 nhanh gap {r1['total'] / r2['total']:.1f}x "
                      f"({r1['total']:.1f}s -> {r2['total']:.1f}s)")

    print("\n" + "=" * 68)


if __name__ == "__main__":
    main()
