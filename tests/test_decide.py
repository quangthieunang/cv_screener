"""Test luat ra quyet dinh (nodes/decide_node.py).

Trong tam: cac gia tri BIEN cua nguong (dung bang 75, dung bang 50) va thu tu uu tien
giua cac luat - day la cho de sai nhat va hau qua truc tiep la moi/loai nham nguoi.
"""
import pytest

from config import INVITE_THRESHOLD, REJECT_THRESHOLD
from nodes.decide_node import _decide, decide_node


def _sr(score, passed=True):
    return {"score": score, "hard_filter_passed": passed}


def _cv(ok=True):
    return {"name": "A", "email": "a@x.com", "extraction_ok": ok}


# ── Nguong ──

@pytest.mark.parametrize("score,expected", [
    (100, "invite"),
    (76,  "invite"),
    (75,  "invite"),   # bien duoi cua invite - PHAI la invite
    (74,  "hold"),
    (60,  "hold"),
    (50,  "hold"),     # bien duoi cua hold - PHAI la hold
    (49,  "reject"),
    (0,   "reject"),
])
def test_nguong_quyet_dinh(jd, score, expected):
    assert _decide(_sr(score), _cv(), jd) == expected


def test_jd_ghi_de_duoc_nguong(jd):
    jd["thresholds"] = {"invite": 90, "reject": 70}
    assert _decide(_sr(85), _cv(), jd) == "hold"
    assert _decide(_sr(90), _cv(), jd) == "invite"
    assert _decide(_sr(69), _cv(), jd) == "reject"


def test_jd_khong_co_thresholds_thi_dung_mac_dinh_config(jd):
    """Doc nguong tu config chu khong hardcode - doi hieu chuan thi test khong gay."""
    jd.pop("thresholds")
    assert _decide(_sr(INVITE_THRESHOLD), _cv(), jd) == "invite"
    assert _decide(_sr(INVITE_THRESHOLD - 1), _cv(), jd) == "hold"
    assert _decide(_sr(REJECT_THRESHOLD), _cv(), jd) == "hold"
    assert _decide(_sr(REJECT_THRESHOLD - 1), _cv(), jd) == "reject"


# ── Thu tu uu tien giua cac luat ──

def test_rot_loc_cung_thi_reject_du_diem_cao(jd):
    """Diem tham khao co the cao, nhung thieu tieu chi bat buoc la loai."""
    assert _decide(_sr(95, passed=False), _cv(), jd) == "reject"


def test_CV_khong_doc_duoc_thi_manual_review_chu_khong_loai(jd):
    """CV scan anh khong duoc tu dong loai - phai de nguoi xem."""
    assert _decide(_sr(0, passed=False), _cv(ok=False), jd) == "manual_review"


def test_manual_review_uu_tien_cao_hon_loc_cung(jd):
    assert _decide(_sr(90, passed=True), _cv(ok=False), jd) == "manual_review"


# ── decide_node: chi invite/reject moi sinh email ──

@pytest.fixture
def fake_email(monkeypatch):
    calls = []

    def _fake(candidate, action, dry_run=None, out_dir=None):
        calls.append({"candidate": candidate, "action": action,
                      "dry_run": dry_run, "out_dir": out_dir})
        return {"action": action, "status": "draft", "path": "x.txt"}

    monkeypatch.setattr("nodes.decide_node.send_hr_email", _fake)
    return calls


def _state(jd, score, passed=True, ok=True):
    return {
        "pdf_path": "cv.pdf", "jd": jd,
        "cv_data": {"name": "Tran Thi B", "email": "b@x.com", "extraction_ok": ok},
        "score_result": _sr(score, passed),
        "decision": None, "email_result": None, "errors": [],
    }


def test_invite_sinh_email_nhap(jd, fake_email):
    out = decide_node(_state(jd, 80))
    assert out["decision"] == "invite"
    assert len(fake_email) == 1
    assert fake_email[0]["action"] == "invite"
    assert out["email_result"]["status"] == "draft"


def test_reject_sinh_email_nhap(jd, fake_email):
    out = decide_node(_state(jd, 30))
    assert out["decision"] == "reject"
    assert fake_email[0]["action"] == "reject"


def test_hold_khong_sinh_email(jd, fake_email):
    out = decide_node(_state(jd, 60))
    assert out["decision"] == "hold"
    assert fake_email == []
    assert out["email_result"]["status"] == "skipped"


def test_manual_review_khong_sinh_email(jd, fake_email):
    out = decide_node(_state(jd, 0, passed=False, ok=False))
    assert out["decision"] == "manual_review"
    assert fake_email == []


def test_node_luon_dry_run_khong_bao_gio_gui_that(jd, fake_email):
    """Gui that chi xay ra o main.py --send sau khi nguoi dung xac nhan."""
    decide_node(_state(jd, 80))
    assert fake_email[0]["dry_run"] is True


def test_nguoi_nhan_lay_tu_cv_data_khong_phai_tu_noi_dung_khac(jd, fake_email):
    st = _state(jd, 80)
    st["cv_data"]["email"] = "that@x.com"
    decide_node(st)
    assert fake_email[0]["candidate"]["email"] == "that@x.com"


def test_thieu_score_result_van_khong_vo(jd, fake_email):
    st = _state(jd, 80)
    st["score_result"] = None
    out = decide_node(st)
    assert out["decision"] == "reject"      # khong co diem -> khong the moi


# ── Hieu chuan nguong (xem giai thich trong config.py) ──

def test_nguong_mac_dinh_nam_trong_dai_diem_thuc_te():
    """Ho so qua loc cung co SAN diem ~63 (tieu chi bat buoc duoc tinh diem lan hai).

    Nguong duoi 63 se lam nhanh "reject vi diem thap" thanh code chet: khong ai qua
    loc cung ma duoi nguong do. Test nay giu cho hieu chuan khong troi ve lai 75/50.
    """
    assert REJECT_THRESHOLD > 63, "reject se khong bao gio chay -> nhanh chet"
    assert INVITE_THRESHOLD > REJECT_THRESHOLD
    assert INVITE_THRESHOLD <= 100


# ── Xung ho: khong dung ten do heuristic doan ──

def test_ten_do_doan_thi_KHONG_dung_de_xung_ho_trong_email(jd, fake_email):
    """Ho so bi tien loc chan -> ten do _guess_name doan. Goi sai ten mot nguoi la
    loi khong sua duoc sau khi email da gui -> phai lui ve xung ho chung chung."""
    st = _state(jd, 0, passed=False)
    st["cv_data"] = {"name": "Cong Ty ABC", "email": "c@x.com",
                     "extraction_ok": True, "name_guessed": True}
    decide_node(st)
    assert fake_email[0]["candidate"]["name"] == ""


def test_ten_do_LLM_boc_tach_thi_van_dung_de_xung_ho(jd, fake_email):
    st = _state(jd, 90)
    st["cv_data"]["name_guessed"] = False
    decide_node(st)
    assert fake_email[0]["candidate"]["name"] == "Tran Thi B"


# ── Ten file ban nhap phai duy nhat theo file CV ──

def test_truyen_ref_la_ten_file_cv_de_ban_nhap_khong_trung(jd, fake_email):
    """Hai ung vien TRUNG HO TEN se ghi de ban nhap cua nhau neu dat ten theo ten nguoi."""
    st = _state(jd, 90)
    st["pdf_path"] = "data/cvs/cv_042_tran_thi_b.pdf"
    decide_node(st)
    assert fake_email[0]["candidate"]["ref"] == "data/cvs/cv_042_tran_thi_b.pdf"


def test_ban_nhap_di_theo_thu_muc_out_cua_jd(jd, fake_email):
    jd["outputs"] = {"email_dir": "/tmp/abc/emails"}
    decide_node(_state(jd, 90))
    assert fake_email[0]["out_dir"] == "/tmp/abc/emails"
