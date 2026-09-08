"""
CLI chinh cua HR CV Screener Agent.

Quet ca thu muc CV (PDF) -> chay pipeline extract -> score -> decide cho tung ho so
-> xuat bao cao xep hang + candidates.json + cac ban nhap email.

Su dung:
  python main.py                              # dung mac dinh: data/jd.json + data/cvs/
  python main.py --cvs data/cvs --limit 3     # chi xu ly 3 ho so dau (de test)
  python main.py --jd data/jd.json --send     # xu ly + GUI EMAIL THAT (co xac nhan)
  python main.py --no-prefilter               # tat tien loc (goi LLM cho moi ho so)
  python main.py --no-cache                   # tat cache boc tach (luon goi LLM lai)
  python main.py --no-dedupe                  # tat chong trung ung vien

Che do --send: sau khi cham diem, in tom tat + danh sach nguoi nhan, HOI xac nhan
(y/N) roi moi goi SMTP gui that. Day la diem nguoi dung truc tiep phe duyet.
"""
import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix encoding cho Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

from config import JD_PATH, CVS_DIR, OUTPUTS_DIR
from graph import screen_cv
from cache import cache_for
from dedupe import dedupe_candidates
from tools.email_tool import send_hr_email

# Nhan hien thi cho tung quyet dinh
DECISION_LABEL = {
    "invite": "✅ Moi phong van",
    "hold": "🟡 Giu lai (can xem them)",
    "reject": "❌ Tu choi",
    "manual_review": "🔎 Review thu cong",
}
DECISION_ORDER = {"invite": 0, "hold": 1, "manual_review": 2, "reject": 3}


def collect_candidate(pdf_path: str, result: dict) -> dict:
    """Rut gon state cuoi cua 1 ung vien thanh ban ghi cho report/json."""
    cv = result.get("cv_data") or {}
    sr = result.get("score_result") or {}
    er = result.get("email_result") or {}
    return {
        "file": os.path.basename(pdf_path),
        "name": cv.get("name", ""),
        "email": cv.get("email", ""),
        "phone": cv.get("phone", ""),          # dung de chong trung ung vien
        "name_guessed": bool(cv.get("name_guessed")),   # ten do heuristic doan, chua qua LLM
        "score": sr.get("score", 0),
        "decision": result.get("decision", "reject"),
        "prefilter_passed": cv.get("prefilter_passed", True),
        "hard_filter_passed": sr.get("hard_filter_passed", False),
        "hard_filter_failures": sr.get("hard_filter_failures", []),
        "matched_skills": sr.get("matched_skills", []),
        "missing_skills": sr.get("missing_skills", []),
        "reasons": sr.get("reasons", []),
        "email_status": er.get("status"),
        "email_path": er.get("path"),
    }


def run_batch(jd: dict, cvs_dir, limit=None):
    """Chay pipeline cho tat ca PDF trong cvs_dir. Tra ve list ban ghi ung vien."""
    pdfs = sorted(Path(cvs_dir).glob("*.pdf"))
    if limit:
        pdfs = pdfs[:limit]

    if not pdfs:
        print(f"⚠️  Khong tim thay PDF nao trong {cvs_dir}")
        return []

    print(f"\n{'='*64}")
    print(f"📄 Vi tri: {jd.get('position', 'N/A')}")
    print(f"📂 Xu ly {len(pdfs)} ho so tu: {cvs_dir}")
    print(f"{'='*64}")

    candidates = []
    for i, pdf in enumerate(pdfs, 1):
        print(f"\n[{i}/{len(pdfs)}] {pdf.name} ...", flush=True)
        try:
            result = screen_cv(str(pdf), jd)
        except Exception as e:
            print(f"   ⚠️  Loi xu ly: {e}")
            candidates.append({
                "file": pdf.name, "name": "", "email": "", "phone": "", "score": 0,
                "name_guessed": False,
                "decision": "manual_review", "prefilter_passed": True,
                "hard_filter_passed": False,
                "hard_filter_failures": [str(e)], "matched_skills": [],
                "missing_skills": [], "reasons": [str(e)],
                "email_status": None, "email_path": None,
            })
            continue
        rec = collect_candidate(str(pdf), result)
        candidates.append(rec)
        tag = "" if rec.get("prefilter_passed", True) else "  ⚡tien loc"
        print(f"   -> {rec['name'] or '(khong ro ten)'} | diem {rec['score']} | "
              f"{DECISION_LABEL.get(rec['decision'], rec['decision'])}{tag}")

    # Xep hang: theo quyet dinh (invite truoc) roi theo diem giam dan
    candidates.sort(key=lambda c: (DECISION_ORDER.get(c["decision"], 9), -c["score"]))
    return candidates


def build_report(jd: dict, candidates: list, dup_stats: dict = None,
                 cache_stats: dict = None) -> str:
    """Tao bao cao Markdown xep hang."""
    dup_stats = dup_stats or {"groups": [], "suspects": [], "duplicates_marked": 0}
    counts = {}
    for c in candidates:
        counts[c["decision"]] = counts.get(c["decision"], 0) + 1
    n_prefiltered = sum(1 for c in candidates if not c.get("prefilter_passed", True))

    lines = []
    lines.append(f"# 📋 Bao Cao Loc Ho So - {jd.get('position', 'N/A')}")
    lines.append("")
    lines.append(f"- Tong so ho so: **{len(candidates)}**")
    for dec in ("invite", "hold", "manual_review", "reject"):
        if counts.get(dec):
            lines.append(f"- {DECISION_LABEL[dec]}: **{counts[dec]}**")
    if n_prefiltered:
        lines.append(f"- ⚡ Bi tien loc tu khoa chan (khong ton lan goi LLM): **{n_prefiltered}**")
    if cache_stats and cache_stats.get("hits"):
        lines.append(f"- 💾 Lay tu cache boc tach (khong ton lan goi LLM): **{cache_stats['hits']}**")
    if dup_stats["duplicates_marked"]:
        lines.append(f"- 👥 Ban ghi trung ung vien: **{dup_stats['duplicates_marked']}** "
                     f"(trong {len(dup_stats['groups'])} nhom)")
    lines.append("")
    lines.append("## 📊 Bang Xep Hang")
    lines.append("")
    lines.append("| # | Ten | Diem | Quyet dinh | Email | Ky nang khop | Ky nang thieu |")
    lines.append("|---|-----|------|-----------|-------|--------------|---------------|")
    for i, c in enumerate(candidates, 1):
        matched = ", ".join(c["matched_skills"]) or "-"
        missing = ", ".join(c["missing_skills"]) or "-"
        name = c["name"] or c["file"]
        if c.get("name_guessed"):
            name += " *(ten doan tu dong dau CV - can kiem tra)*"
        if c.get("duplicate_of"):
            name += f" *(trung voi {c['duplicate_of']})*"
        lines.append(
            f"| {i} | {name} | {c['score']} | "
            f"{DECISION_LABEL.get(c['decision'], c['decision'])} | {c['email'] or '-'} | "
            f"{matched} | {missing} |"
        )
    lines.append("")

    # Nhom ho so trung nguoi - chi ban chinh duoc gui email.
    if dup_stats["groups"]:
        lines.append("## 👥 Ho So Trung Ung Vien")
        lines.append("")
        lines.append("Chi **ban chinh** (diem cao nhat moi nhom) duoc gui email; cac ban con lai bo qua.")
        lines.append("")
        for grp in dup_stats["groups"]:
            primary = grp[0]
            lines.append(f"- **{primary['name'] or primary['file']}** "
                         f"({primary['email'] or 'khong co email'}) - ban chinh: "
                         f"`{primary['file']}` (diem {primary['score']})")
            for c in grp[1:]:
                lines.append(f"  - trung: `{c['file']}` (diem {c['score']})")
        lines.append("")

    if dup_stats["suspects"]:
        lines.append("## ⚠️ Nghi Ngo Trung (chi trung ho ten - can HR kiem tra)")
        lines.append("")
        for grp in dup_stats["suspects"]:
            files = ", ".join(f"`{c['file']}`" for c in grp)
            lines.append(f"- **{grp[0]['name']}**: {files}")
        lines.append("")

    # Chi tiet ly do cho ho so bi tu choi vi loc cung (giup HR kiem chung)
    rejected = [c for c in candidates if not c["hard_filter_passed"]
                and c["decision"] in ("reject", "manual_review")]
    if rejected:
        lines.append("## ❌ Ho So Khong Dat Tieu Chi Bat Buoc")
        lines.append("")
        for c in rejected:
            fails = "; ".join(c["hard_filter_failures"]) or "khong ro"
            lines.append(f"- **{c['name'] or c['file']}**: {fails}")
        lines.append("")

    return "\n".join(lines)


def save_outputs(report_md: str, candidates: list, out_dir):
    """Ghi report_ranked.md + candidates.json."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    report_path = out / "report_ranked.md"
    report_path.write_text(report_md, encoding="utf-8")

    json_path = out / "candidates.json"
    json_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")

    return report_path, json_path


def do_send(jd: dict, candidates: list, out_dir):
    """Che do --send: xem truoc -> XAC NHAN -> gui email that qua SMTP."""

    # Chi gui cho invite/reject co email hop le (email_status='draft' nghia la co email).
    # Bo qua ban ghi trung: mot nguoi chi nhan DUNG MOT email trong mot dot tuyen.
    to_send = [c for c in candidates
               if c["decision"] in ("invite", "reject")
               and c["email_status"] == "draft"
               and not c.get("duplicate_of")]

    n_skipped_dup = sum(1 for c in candidates
                        if c.get("duplicate_of") and c["email_status"] == "draft")
    if n_skipped_dup:
        print(f"\n👥 Bo qua {n_skipped_dup} ban ghi trung ung vien (khong gui email lap).")

    if not to_send:
        print("\n(Khong co email hop le nao de gui.)")
        return

    n_invite = sum(1 for c in to_send if c["decision"] == "invite")
    n_reject = sum(1 for c in to_send if c["decision"] == "reject")

    print(f"\n{'='*64}")
    print(f"✉️  CHUAN BI GUI EMAIL THAT")
    print(f"{'='*64}")
    print(f"   Moi phong van: {n_invite}   |   Tu choi: {n_reject}   |   Tong: {len(to_send)}")
    print("   Danh sach nguoi nhan:")
    for c in to_send:
        print(f"     - [{c['decision']}] {c['name']} <{c['email']}>")

    # Cong an toan: bat buoc xac nhan tuong minh tu nguoi dung.
    # Neu khong co dau vao (EOF/khong tuong tac) -> HUY gui de an toan.
    try:
        answer = input("\n❓ Xac nhan GUI THAT toi cac dia chi tren? (y/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n⚠️  Khong nhan duoc xac nhan (khong o che do tuong tac) -> HUY gui de an toan.")
        print("   Hay chay lenh nay truc tiep trong terminal de xac nhan gui.")
        return
    if answer != "y":
        print("Da HUY. Khong gui email nao.")
        return

    sent_log = []
    for c in to_send:
        # Ten do heuristic doan (ho so bi tien loc chan) KHONG duoc dung de xung ho -
        # cung quy tac nhu decide_node. Day la duong gui THAT nen cang phai giu.
        candidate = {
            "name": "" if c.get("name_guessed") else c["name"],
            "email": c["email"],
            "position": jd.get("position", ""),
            "ref": c["file"],
        }
        res = send_hr_email(candidate, c["decision"], dry_run=False)
        status = res.get("status")
        mark = "✅" if status == "sent" else "⚠️"
        print(f"   {mark} {c['email']}: {status}" + (f" ({res.get('error')})" if res.get("error") else ""))
        sent_log.append({
            "name": c["name"], "email": c["email"], "action": c["decision"],
            "status": status, "error": res.get("error"),
            "sent_at": datetime.now().isoformat(timespec="seconds"),
        })

    log_path = Path(out_dir) / "sent_log.json"
    log_path.write_text(json.dumps(sent_log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 Da ghi nhat ky gui: {log_path}")


def main():
    parser = argparse.ArgumentParser(
        description="HR CV Screener Agent - loc & cham diem CV theo JD.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--jd", type=str, default=str(JD_PATH), help="Duong dan file JD (jd.json)")
    parser.add_argument("--cvs", type=str, default=str(CVS_DIR), help="Thu muc chua CV (PDF)")
    parser.add_argument("--out", type=str, default=str(OUTPUTS_DIR), help="Thu muc xuat ket qua")
    parser.add_argument("--limit", type=int, default=None, help="Chi xu ly N ho so dau (de test)")
    parser.add_argument("--send", action="store_true", help="GUI EMAIL THAT qua SMTP (co xac nhan)")
    parser.add_argument("--no-prefilter", action="store_true",
                        help="Tat tien loc tu khoa (goi LLM boc tach cho MOI ho so)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Tat cache boc tach theo hash PDF (luon goi LLM lai)")
    parser.add_argument("--no-dedupe", action="store_true",
                        help="Tat chong trung ung vien")
    args = parser.parse_args()

    if not os.path.exists(args.jd):
        print(f"❌ Khong tim thay JD: {args.jd}")
        return
    with open(args.jd, "r", encoding="utf-8") as f:
        jd = json.load(f)

    if args.no_prefilter:
        jd.setdefault("prefilter", {})["enabled"] = False
    if args.no_cache:
        jd.setdefault("cache", {})["enabled"] = False
    # Ban nhap email di theo --out de bao cao va email luon nam cung mot cho.
    email_dir = Path(args.out) / "emails"
    jd.setdefault("outputs", {})["email_dir"] = str(email_dir)

    candidates = run_batch(jd, args.cvs, limit=args.limit)
    if not candidates:
        return

    dup_stats = ({"groups": [], "suspects": [], "duplicates_marked": 0}
                 if args.no_dedupe else dedupe_candidates(candidates))
    cache_stats = cache_for(jd).stats()

    report_md = build_report(jd, candidates, dup_stats, cache_stats)
    report_path, json_path = save_outputs(report_md, candidates, args.out)

    n_prefiltered = sum(1 for c in candidates if not c.get("prefilter_passed", True))

    print(f"\n{'='*64}")
    print("✅ HOAN TAT")
    if n_prefiltered:
        print(f"   ⚡ Tien loc chan:  {n_prefiltered}/{len(candidates)} ho so (khong goi LLM)")
    if cache_stats["enabled"]:
        print(f"   💾 Cache boc tach: {cache_stats['hits']} lay lai / "
              f"{cache_stats['writes']} ghi moi (khong goi LLM: {cache_stats['hits']})")
    if dup_stats["duplicates_marked"]:
        print(f"   👥 Ban ghi trung:  {dup_stats['duplicates_marked']} "
              f"(trong {len(dup_stats['groups'])} nhom)")
    if dup_stats["suspects"]:
        print(f"   ⚠️  Nghi ngo trung ten: {len(dup_stats['suspects'])} nhom - xem bao cao")
    print(f"   Bao cao xep hang: {report_path}")
    print(f"   Du lieu JSON:     {json_path}")
    print(f"   Ban nhap email:   {email_dir}")
    print(f"{'='*64}")

    if args.send:
        do_send(jd, candidates, args.out)
    else:
        print("\nℹ️  Che do nhap (dry-run): email chi duoc SOAN, chua gui.")
        print("   Them co --send de gui that (se hoi xac nhan truoc khi gui).")


if __name__ == "__main__":
    main()
