"""
Tool 3: send_hr_email(candidate, action)

Soan (va tuy chon GUI THAT) email cho ung vien:
  - action="invite"  -> thu moi phong van.
  - action="reject"  -> thu tu choi lich su.

An toan:
  - Mac dinh DRY-RUN (config.EMAIL_DRY_RUN=True): chi ghi ban nhap ra file .txt,
    KHONG gui that. main.py --send se truyen dry_run=False de gui that.
  - Nguoi nhan chi lay tu candidate["email"] (da bóc tách tu CV) - khong bao gio
    lay dia chi tu chi dan nam trong noi dung CV.
  - Thong tin dang nhap SMTP chi doc tu bien moi truong (.env), khong hardcode.

Tool KHONG raise: loi tra ve dict co khoa "status"="error" + "error".

Chay truc tiep de smoke test (sinh nhap invite + reject, khong gui that):
    python tools/email_tool.py
"""
import os
import re
import sys
import smtplib
from email.message import EmailMessage
from pathlib import Path

_CURRENT = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_CURRENT)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

# Dung lai normalize_name cua dedupe.py (bo dau tieng Viet + ha chu thuong) thay vi
# viet lai - de ten file ban nhap va khoa chong trung chuan hoa ten y het nhau.
from dedupe import normalize_name
from config import (
    EMAIL_DIR, EMAIL_DRY_RUN,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM,
)

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

# ── Mau email tieng Viet ──

INVITE_SUBJECT = "Thu moi phong van - Vi tri {position}"
INVITE_BODY = """Kinh gui anh/chi {name},

Cam on anh/chi da ung tuyen vao vi tri {position} tai cong ty chung toi.

Sau khi xem xet ho so, chung toi rat an tuong voi kinh nghiem va ky nang cua anh/chi,
va tran trong moi anh/chi tham gia buoi phong van de trao doi chi tiet hon.

Bo phan Nhan su se lien he trong thoi gian som nhat de thong nhat lich phong van
phu hop voi anh/chi.

Tran trong,
Bo phan Nhan su
"""

REJECT_SUBJECT = "Ket qua ung tuyen - Vi tri {position}"
REJECT_BODY = """Kinh gui anh/chi {name},

Cam on anh/chi da danh thoi gian ung tuyen vao vi tri {position} tai cong ty chung toi.

Sau khi can nhac ky luong, rat tiec chung toi chua the tiep tuc voi ho so cua anh/chi
o vi tri nay tai thoi diem hien tai. Day la mot quyet dinh kho khan boi chung toi nhan
duoc rat nhieu ho so chat luong.

Chung toi se luu ho so cua anh/chi va rat mong co co hoi hop tac trong tuong lai.
Kinh chuc anh/chi som tim duoc cong viec phu hop.

Tran trong,
Bo phan Nhan su
"""

_TEMPLATES = {
    "invite": (INVITE_SUBJECT, INVITE_BODY),
    "reject": (REJECT_SUBJECT, REJECT_BODY),
}


def _slug(text: str) -> str:
    """Ten file an toan tu ho ten ung vien.

    Bo dau tieng Viet TRUOC khi loc ky tu, neu khong "Nguyễn Văn A" thanh
    "nguy_n_v_n_a" (moi chu co dau bien thanh dau gach) - ten file kho doc va hai
    ung vien khac nhau de tao ra cung mot slug hon.
    """
    text = normalize_name(text) or "candidate"
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "candidate"


def _send_smtp(msg: EmailMessage) -> None:
    """Gui email that qua SMTP (STARTTLS). Nem exception neu that bai."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        raise RuntimeError("Thieu cau hinh SMTP (SMTP_HOST/USER/PASS) trong .env")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


def send_hr_email(candidate: dict, action: str, dry_run: bool = None,
                  out_dir=None) -> dict:
    """Soan/gui email theo action. Tra ve email_result (Contract 3).

    candidate: {"name": ..., "email": ..., "position": ..., "ref": <tuy chon>}
        "ref" (thuong la ten file CV) chi dung de dat TEN FILE ban nhap cho duy nhat.
        Khong co ref thi lui ve dat ten theo ho ten - luc do hai ung vien TRUNG HO TEN
        se ghi de ban nhap cua nhau ma khong bao. Ho ten Viet Nam trung nhau rat pho
        bien va dedupe.py co y KHONG gop nhom "chi trung ten", nen day la tinh huong
        that su xay ra chu khong phai gia dinh.
    action: "invite" | "reject"
    dry_run: None -> dung config.EMAIL_DRY_RUN. True -> chi ghi nhap. False -> gui that.
    out_dir: thu muc ghi ban nhap. None -> config.EMAIL_DIR. main.py truyen theo co --out
        de bao cao va ban nhap luon nam cung mot cho.
    """
    if action not in _TEMPLATES:
        return {"action": action, "status": "error", "error": f"action khong hop le: {action}"}

    if dry_run is None:
        dry_run = EMAIL_DRY_RUN

    name = (candidate.get("name") or "ung vien").strip()
    recipient = (candidate.get("email") or "").strip()
    position = (candidate.get("position") or "").strip()

    subject_tpl, body_tpl = _TEMPLATES[action]
    subject = subject_tpl.format(position=position or "ung tuyen")
    body = body_tpl.format(name=name, position=position or "ung tuyen")

    result = {
        "action": action,
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "status": None,
    }

    # Khong co email hop le -> khong the gui, chi ghi nhap de HR xu ly tay.
    valid_email = bool(_EMAIL_RE.match(recipient))

    if dry_run or not valid_email:
        email_dir = Path(out_dir) if out_dir else EMAIL_DIR
        email_dir.mkdir(parents=True, exist_ok=True)
        # ref (ten file CV) la duy nhat trong mot dot tuyen -> uu tien dung lam ten file.
        ref = (candidate.get("ref") or "").strip()
        stem = _slug(os.path.splitext(os.path.basename(ref))[0]) if ref else _slug(name)
        path = email_dir / f"{action}_{stem}.txt"
        content = (
            f"To: {recipient or '(KHONG CO EMAIL - can review thu cong)'}\n"
            f"From: {SMTP_FROM or 'HR Team'}\n"
            f"Subject: {subject}\n"
            f"{'-' * 50}\n{body}"
        )
        path.write_text(content, encoding="utf-8")
        result["path"] = str(path)
        result["status"] = "draft" if valid_email else "skipped"
        if not valid_email:
            result["error"] = "Khong co dia chi email hop le trong CV"
        return result

    # Gui that
    try:
        msg = EmailMessage()
        msg["From"] = SMTP_FROM or SMTP_USER
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.set_content(body)
        _send_smtp(msg)
        result["status"] = "sent"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    import json
    mock = {"name": "Tran Thi B", "email": "tranthib.dev@gmail.com", "position": "Backend Engineer (Python)"}
    mock_no_email = {"name": "Nguoi Khong Email", "email": "", "position": "Backend Engineer (Python)"}

    print("=== INVITE (dry-run) ===")
    print(json.dumps(send_hr_email(mock, "invite", dry_run=True), ensure_ascii=False, indent=2))
    print("\n=== REJECT (dry-run) ===")
    print(json.dumps(send_hr_email(mock, "reject", dry_run=True), ensure_ascii=False, indent=2))
    print("\n=== INVITE nhung THIEU email (status=skipped) ===")
    print(json.dumps(send_hr_email(mock_no_email, "invite", dry_run=True), ensure_ascii=False, indent=2))
