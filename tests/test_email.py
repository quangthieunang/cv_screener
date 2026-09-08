"""Test Tool 3 - soan/gui email (tools/email_tool.py).

Trong tam: KHONG test nao duoc gui email that. Moi test dung dry_run=True hoac
out_dir=tmp_path; nhanh SMTP chi duoc kiem tra qua monkeypatch.
"""
import pytest

from tools.email_tool import _slug, send_hr_email


def _cand(name="Tran Thi B", email="b@example.com", **kw):
    d = {"name": name, "email": email, "position": "Backend Engineer (Python)"}
    d.update(kw)
    return d


# ── Ban nhap ──

def test_invite_sinh_ban_nhap_dung_noi_dung(tmp_path):
    r = send_hr_email(_cand(), "invite", dry_run=True, out_dir=tmp_path)
    assert r["status"] == "draft"
    assert r["recipient"] == "b@example.com"
    assert "Tran Thi B" in r["body"]
    assert "Backend Engineer (Python)" in r["subject"]
    assert "phong van" in r["body"].lower()


def test_reject_dung_mau_tu_choi(tmp_path):
    r = send_hr_email(_cand(), "reject", dry_run=True, out_dir=tmp_path)
    assert r["status"] == "draft"
    assert "rat tiec" in r["body"].lower()


def test_ban_nhap_duoc_ghi_ra_file(tmp_path):
    r = send_hr_email(_cand(), "invite", dry_run=True, out_dir=tmp_path)
    content = (tmp_path / "invite_tran_thi_b.txt").read_text(encoding="utf-8")
    assert r["path"].endswith("invite_tran_thi_b.txt")
    assert "To: b@example.com" in content
    assert "Subject:" in content


def test_action_khong_hop_le_tra_ve_error(tmp_path):
    r = send_hr_email(_cand(), "hold", dry_run=True, out_dir=tmp_path)
    assert r["status"] == "error"


# ── Thieu email -> skipped, khong bao gio gui ──

def test_thieu_email_thi_status_skipped(tmp_path):
    r = send_hr_email(_cand(email=""), "invite", dry_run=True, out_dir=tmp_path)
    assert r["status"] == "skipped"
    assert "error" in r


@pytest.mark.parametrize("bad", ["khong-phai-email", "a@b", "@x.com", "a b@x.com", "   "])
def test_email_sai_dinh_dang_thi_skipped(bad, tmp_path):
    r = send_hr_email(_cand(email=bad), "invite", dry_run=True, out_dir=tmp_path)
    assert r["status"] == "skipped"


def test_email_khong_hop_le_thi_KHONG_goi_SMTP_du_da_tat_dry_run(tmp_path, monkeypatch):
    """dry_run=False + email rac -> phai ghi nhap, tuyet doi khong cham SMTP."""
    called = []
    monkeypatch.setattr("tools.email_tool._send_smtp", lambda msg: called.append(msg))
    monkeypatch.setattr("tools.email_tool.EMAIL_DIR", tmp_path)
    r = send_hr_email(_cand(email="rac"), "invite", dry_run=False)
    assert r["status"] == "skipped"
    assert called == []


def test_thieu_ten_thi_xung_ho_chung_chung(tmp_path):
    r = send_hr_email(_cand(name=""), "reject", dry_run=True, out_dir=tmp_path)
    assert "ung vien" in r["body"]


# ── Ten file ban nhap phai duy nhat ──

def test_hai_ung_vien_trung_ho_ten_khong_ghi_de_ban_nhap_cua_nhau(tmp_path):
    """Loi cu: ten file chi theo ho ten -> ban nhap thu hai ghi de ban thu nhat."""
    r1 = send_hr_email(_cand(email="b1@x.com", ref="data/cvs/cv_007.pdf"),
                       "reject", dry_run=True, out_dir=tmp_path)
    r2 = send_hr_email(_cand(email="b2@x.com", ref="data/cvs/cv_042.pdf"),
                       "reject", dry_run=True, out_dir=tmp_path)
    assert r1["path"] != r2["path"]
    assert len(list(tmp_path.glob("reject_*.txt"))) == 2
    assert "b1@x.com" in (tmp_path / "reject_cv_007.txt").read_text(encoding="utf-8")


def test_khong_co_ref_thi_lui_ve_dat_ten_theo_ho_ten(tmp_path):
    r = send_hr_email(_cand(), "invite", dry_run=True, out_dir=tmp_path)
    assert r["path"].endswith("invite_tran_thi_b.txt")


def test_invite_va_reject_cua_cung_file_khong_de_nhau(tmp_path):
    a = send_hr_email(_cand(ref="cv_1.pdf"), "invite", dry_run=True, out_dir=tmp_path)
    b = send_hr_email(_cand(ref="cv_1.pdf"), "reject", dry_run=True, out_dir=tmp_path)
    assert a["path"] != b["path"]


@pytest.mark.parametrize("raw,expected", [
    ("Tran Thi B", "tran_thi_b"), ("  A--B  ", "a_b"), ("", "candidate"),
    ("Nguyễn Văn A", "nguyen_van_a"),   # bo dau truoc khi loc ky tu
    ("Đỗ Đình Đ", "do_dinh_d"),
])
def test_slug_ten_file_an_toan(raw, expected):
    assert _slug(raw) == expected


# ── Gui that ──

def test_gui_that_goi_SMTP_va_tra_sent(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr("tools.email_tool._send_smtp", lambda msg: sent.append(msg))
    r = send_hr_email(_cand(), "invite", dry_run=False)
    assert r["status"] == "sent"
    assert len(sent) == 1
    assert sent[0]["To"] == "b@example.com"


def test_SMTP_loi_thi_tra_error_chu_khong_raise(monkeypatch):
    def _boom(msg):
        raise RuntimeError("SMTP tu choi dang nhap")
    monkeypatch.setattr("tools.email_tool._send_smtp", _boom)
    r = send_hr_email(_cand(), "invite", dry_run=False)
    assert r["status"] == "error"
    assert "SMTP" in r["error"]


def test_thieu_cau_hinh_SMTP_thi_bao_loi_ro_rang(monkeypatch):
    monkeypatch.setattr("tools.email_tool.SMTP_HOST", "")
    r = send_hr_email(_cand(), "invite", dry_run=False)
    assert r["status"] == "error"
    assert "SMTP" in r["error"]
