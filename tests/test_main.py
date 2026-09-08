"""Test cong gui email that va bao cao (main.py).

do_send() la ham NGUY HIEM NHAT trong project: no la duong duy nhat gui email ra ngoai.
Moi test o day monkeypatch send_hr_email nen KHONG co email nao that su duoc gui, va
kiem chung tung cong an toan mot:
    - khong xac nhan / xac nhan khac 'y'  -> khong gui gi
    - khong o che do tuong tac (EOF)      -> khong gui gi
    - chi gui invite/reject co email hop le, bo qua ban trung
    - khong dung ten do heuristic doan de xung ho
"""
import json

import pytest

from main import build_report, collect_candidate, do_send


def _rec(file="cv.pdf", name="Tran Thi B", email="b@x.com", decision="invite",
         score=90, email_status="draft", **kw):
    rec = {
        "file": file, "name": name, "email": email, "phone": "", "score": score,
        "name_guessed": False, "decision": decision, "prefilter_passed": True,
        "hard_filter_passed": True, "hard_filter_failures": [],
        "matched_skills": ["python"], "missing_skills": [], "reasons": [],
        "email_status": email_status, "email_path": None,
    }
    rec.update(kw)
    return rec


@pytest.fixture
def fake_send(monkeypatch):
    """Thay send_hr_email trong main - khong bao gio cham SMTP that."""
    calls = []

    def _fake(candidate, action, dry_run=None, out_dir=None):
        calls.append({"candidate": candidate, "action": action, "dry_run": dry_run})
        return {"action": action, "status": "sent"}

    monkeypatch.setattr("main.send_hr_email", _fake)
    return calls


@pytest.fixture
def answer(monkeypatch):
    """Gia lap nguoi dung go tra loi vao prompt xac nhan."""
    def _set(value):
        if isinstance(value, BaseException):
            def _raise(_prompt=""):
                raise value
            monkeypatch.setattr("builtins.input", _raise)
        else:
            monkeypatch.setattr("builtins.input", lambda _prompt="": value)
    return _set


# ── Cong xac nhan ──

def test_tra_loi_y_thi_moi_gui(jd, fake_send, answer, tmp_path):
    answer("y")
    do_send(jd, [_rec()], tmp_path)
    assert len(fake_send) == 1
    assert fake_send[0]["dry_run"] is False


@pytest.mark.parametrize("reply", ["y", "Y", " y ", "Y\n"])
def test_chap_nhan_y_ke_ca_hoa_thuong_va_khoang_trang(jd, fake_send, answer, tmp_path, reply):
    answer(reply)
    do_send(jd, [_rec()], tmp_path)
    assert len(fake_send) == 1


@pytest.mark.parametrize("reply", ["n", "N", "", "yes dung gui", "co", "y!"])
def test_tra_loi_khac_y_thi_KHONG_gui_gi(jd, fake_send, answer, tmp_path, reply):
    answer(reply)
    do_send(jd, [_rec()], tmp_path)
    assert fake_send == []


def test_khong_tuong_tac_duoc_thi_HUY_gui(jd, fake_send, answer, tmp_path):
    """Chay trong CI/pipe khong co stdin -> phai HUY, khong duoc coi la dong y."""
    answer(EOFError())
    do_send(jd, [_rec()], tmp_path)
    assert fake_send == []


def test_ctrl_c_thi_HUY_gui(jd, fake_send, answer, tmp_path):
    answer(KeyboardInterrupt())
    do_send(jd, [_rec()], tmp_path)
    assert fake_send == []


def test_khong_co_ai_de_gui_thi_khong_hoi_xac_nhan(jd, fake_send, answer, tmp_path):
    answer(RuntimeError("khong duoc goi input()"))
    do_send(jd, [_rec(decision="hold")], tmp_path)
    assert fake_send == []


# ── Chon dung nguoi nhan ──

def test_chi_gui_cho_invite_va_reject(jd, fake_send, answer, tmp_path):
    answer("y")
    do_send(jd, [
        _rec(file="a.pdf", decision="invite"),
        _rec(file="b.pdf", decision="reject"),
        _rec(file="c.pdf", decision="hold"),
        _rec(file="d.pdf", decision="manual_review"),
    ], tmp_path)
    assert sorted(c["action"] for c in fake_send) == ["invite", "reject"]


def test_bo_qua_ho_so_khong_co_email_hop_le(jd, fake_send, answer, tmp_path):
    """email_status='skipped' nghia la Tool 3 khong tim thay email hop le."""
    answer("y")
    do_send(jd, [_rec(email="", email_status="skipped")], tmp_path)
    assert fake_send == []


def test_bo_qua_ban_ghi_trung_de_mot_nguoi_chi_nhan_MOT_email(jd, fake_send, answer, tmp_path):
    answer("y")
    do_send(jd, [_rec(file="v2.pdf", score=90),
                 _rec(file="v1.pdf", score=70, duplicate_of="v2.pdf")], tmp_path)
    assert len(fake_send) == 1
    assert fake_send[0]["candidate"]["ref"] == "v2.pdf"


# ── Khong ro ten thi xung ho chung chung ──

def test_ten_do_doan_thi_khong_dung_de_xung_ho(jd, fake_send, answer, tmp_path):
    answer("y")
    do_send(jd, [_rec(name="Cong Ty ABC", name_guessed=True, decision="reject")], tmp_path)
    assert fake_send[0]["candidate"]["name"] == ""


def test_ten_da_boc_tach_thi_van_dung(jd, fake_send, answer, tmp_path):
    answer("y")
    do_send(jd, [_rec()], tmp_path)
    assert fake_send[0]["candidate"]["name"] == "Tran Thi B"


# ── Nhat ky gui ──

def test_ghi_nhat_ky_gui(jd, fake_send, answer, tmp_path):
    answer("y")
    do_send(jd, [_rec()], tmp_path)
    log = json.loads((tmp_path / "sent_log.json").read_text(encoding="utf-8"))
    assert len(log) == 1
    assert log[0]["email"] == "b@x.com" and log[0]["status"] == "sent"
    assert log[0]["sent_at"]


def test_khong_ghi_nhat_ky_khi_da_huy(jd, fake_send, answer, tmp_path):
    answer("n")
    do_send(jd, [_rec()], tmp_path)
    assert not (tmp_path / "sent_log.json").exists()


# ── Bao cao ──

def test_bao_cao_co_du_cac_muc_chinh(jd):
    md = build_report(jd, [_rec(), _rec(file="b.pdf", decision="hold", score=78)])
    assert "Bang Xep Hang" in md
    assert "Tong so ho so: **2**" in md
    assert "Tran Thi B" in md


def test_bao_cao_gan_nhan_ten_doan(jd):
    md = build_report(jd, [_rec(name="Ai Do", name_guessed=True)])
    assert "ten doan" in md.lower()


def test_bao_cao_neu_ly_do_loai_de_HR_doi_chieu(jd):
    """Bat buoc: HR phai doi chieu duoc vi sao mot ho so bi loai."""
    md = build_report(jd, [_rec(decision="reject", hard_filter_passed=False,
                                hard_filter_failures=["Thieu ky nang bat buoc: sql"])])
    assert "Thieu ky nang bat buoc: sql" in md


def test_bao_cao_neu_so_ho_so_tiet_kiem_duoc_LLM(jd):
    md = build_report(jd, [_rec(prefilter_passed=False, decision="reject")],
                      cache_stats={"hits": 3})
    assert "Bi tien loc" in md and "cache" in md.lower()


def test_bao_cao_liet_ke_nhom_trung_va_nghi_ngo_trung(jd):
    a, b = _rec(file="a.pdf"), _rec(file="b.pdf", duplicate_of="a.pdf")
    md = build_report(jd, [a, b], dup_stats={
        "groups": [[a, b]], "suspects": [[a, b]], "duplicates_marked": 1})
    assert "Ho So Trung Ung Vien" in md
    assert "Nghi Ngo Trung" in md


def test_bao_cao_khong_vo_voi_danh_sach_rong(jd):
    assert "Tong so ho so: **0**" in build_report(jd, [])


# ── collect_candidate ──

def test_collect_candidate_lay_du_truong_cho_dedupe_va_bao_cao():
    result = {
        "cv_data": {"name": "A", "email": "a@x.com", "phone": "0912345678",
                    "prefilter_passed": False, "name_guessed": True},
        "score_result": {"score": 0, "hard_filter_passed": False,
                         "hard_filter_failures": ["tien loc"], "matched_skills": [],
                         "missing_skills": ["python"], "reasons": ["tien loc"]},
        "decision": "reject",
        "email_result": {"status": "draft", "path": "x.txt"},
    }
    rec = collect_candidate("data/cvs/cv_9.pdf", result)
    assert rec["file"] == "cv_9.pdf"
    assert rec["phone"] == "0912345678"        # dedupe can phone
    assert rec["name_guessed"] is True         # email can biet ten co dang tin khong
    assert rec["prefilter_passed"] is False


def test_collect_candidate_state_thieu_thi_khong_vo():
    rec = collect_candidate("cv.pdf", {})
    assert rec["score"] == 0 and rec["decision"] == "reject"
