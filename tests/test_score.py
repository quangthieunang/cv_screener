"""Test Tool 2 - cham diem hybrid (tools/score.py).

Hai dieu quan trong nhat duoc bao ve o day:
  1. Loc cung dung, va KHONG goi LLM khi ho so da rot loc cung (dung cam ket tiet kiem).
  2. Prompt cham 'fit' KHONG chua thong tin nhan khau (ten, email, sdt) -> chong thien vi.
"""
import pytest

from tools.score import score_candidate


# ── Loc cung ──

def test_ung_vien_manh_qua_loc_cung_va_diem_cao(jd, cv_strong, fake_llm):
    r = score_candidate(cv_strong, jd)
    assert r["hard_filter_passed"] is True
    assert r["hard_filter_failures"] == []
    assert r["score"] >= 75
    assert set(r["matched_skills"]) >= {"python", "sql"}


def test_thieu_ky_nang_bat_buoc_thi_rot(jd, cv_strong, fake_llm):
    cv_strong["skills"] = ["python", "docker"]          # thieu sql
    r = score_candidate(cv_strong, jd)
    assert r["hard_filter_passed"] is False
    assert any("sql" in f for f in r["hard_filter_failures"])


def test_thieu_nam_kinh_nghiem_thi_rot(jd, cv_strong, fake_llm):
    cv_strong["years_experience"] = 1.0                 # yeu cau 2
    r = score_candidate(cv_strong, jd)
    assert r["hard_filter_passed"] is False
    assert any("Kinh nghiem" in f for f in r["hard_filter_failures"])


def test_thieu_hoc_van_thi_rot(jd, cv_strong, fake_llm):
    cv_strong["education"] = [{"degree": "college", "field": "CNTT", "school": "CD"}]
    r = score_candidate(cv_strong, jd)
    assert r["hard_filter_passed"] is False
    assert any("Hoc van" in f for f in r["hard_filter_failures"])


def test_bang_cap_cao_hon_yeu_cau_van_dat(jd, cv_strong, fake_llm):
    cv_strong["education"] = [{"degree": "master", "field": "CNTT", "school": "BK"}]
    r = score_candidate(cv_strong, jd)
    assert r["hard_filter_passed"] is True


def test_rot_loc_cung_thi_KHONG_goi_LLM(jd, cv_strong, fake_llm):
    """Day la cam ket tiet kiem chi phi cot loi cua thiet ke - phai co test giu."""
    cv_strong["skills"] = ["excel"]
    score_candidate(cv_strong, jd)
    assert fake_llm.calls == []


def test_qua_loc_cung_thi_CO_goi_LLM(jd, cv_strong, fake_llm):
    score_candidate(cv_strong, jd)
    assert len(fake_llm.calls) == 1


# ── Chong thien vi ──

def test_prompt_fit_khong_chua_thong_tin_nhan_khau(jd, cv_strong, fake_llm):
    """LLM chi duoc thay skills / so nam / hoc van - khong ten, email, sdt."""
    score_candidate(cv_strong, jd)
    prompt, system = fake_llm.calls[0]
    blob = (prompt + system).lower()
    assert "tran thi b" not in blob
    assert "b@example.com" not in blob
    assert "0912345678" not in blob
    assert "python" in blob        # nhung ky nang thi phai co


def test_system_prompt_fit_co_canh_bao_prompt_injection(jd, cv_strong, fake_llm):
    score_candidate(cv_strong, jd)
    _, system = fake_llm.calls[0]
    assert "DU LIEU" in system and "menh lenh" in system


# ── Diem thanh phan ──

def test_diem_hoc_van_kem_mot_bac_duoc_nua_diem(jd, cv_strong, fake_llm):
    cv_strong["education"] = [{"degree": "college", "field": "CNTT", "school": "CD"}]
    r = score_candidate(cv_strong, jd)
    assert r["breakdown"]["education"] == pytest.approx(10.0)   # 0.5 x 20


def test_diem_hoc_van_kem_hai_bac_bang_khong(jd, cv_strong, fake_llm):
    cv_strong["education"] = [{"degree": "highschool", "field": "", "school": ""}]
    r = score_candidate(cv_strong, jd)
    assert r["breakdown"]["education"] == pytest.approx(0.0)


def test_diem_kinh_nghiem_bi_chan_tran(jd, cv_strong, fake_llm):
    """20 nam kinh nghiem khong duoc vuot tran cua thanh phan experience (30)."""
    cv_strong["years_experience"] = 20.0
    r = score_candidate(cv_strong, jd)
    assert r["breakdown"]["experience"] == pytest.approx(30.0)


def test_diem_ky_nang_tinh_theo_ty_le_required_va_nice(jd, cv_strong, fake_llm):
    """Du 100% required + 0% nice-to-have -> 0.7 x 40 = 28."""
    cv_strong["skills"] = ["python", "sql"]
    r = score_candidate(cv_strong, jd)
    assert r["breakdown"]["skills"] == pytest.approx(28.0)
    assert set(r["missing_skills"]) == {"docker", "aws", "kubernetes", "fastapi"}


def test_trong_so_duoc_chuan_hoa_ve_100(jd, cv_strong, fake_llm):
    """Trong so tong 200 van chi cho diem toi da 100 - khong duoc lam trot khung diem."""
    jd["weights"] = {"skills": 80, "experience": 60, "education": 40, "fit": 20}
    cv_strong["skills"] = ["python", "sql", "docker", "aws", "kubernetes", "fastapi"]
    cv_strong["years_experience"] = 10.0
    r = score_candidate(cv_strong, jd)
    assert r["score"] == 100


def test_diem_luon_nam_trong_0_100(jd, cv_strong, fake_llm):
    fake_llm.set({"fit_score": 99.0, "reasons": []})    # LLM tra so ngoai khoang
    cv_strong["years_experience"] = 100.0
    r = score_candidate(cv_strong, jd)
    assert 0 <= r["score"] <= 100


# ── Chiu loi ──

def test_LLM_loi_thi_fit_lay_gia_tri_trung_binh(jd, cv_strong, fake_llm):
    fake_llm.set({"error": "Ollama khong phan hoi"})
    r = score_candidate(cv_strong, jd)
    assert r["breakdown"]["fit"] == pytest.approx(5.0)   # 0.5 x 10
    assert r["hard_filter_passed"] is True               # loi LLM khong duoc lam rot ung vien


def test_LLM_tra_fit_score_rac_khong_lam_vo(jd, cv_strong, fake_llm):
    fake_llm.set({"fit_score": "rat cao", "reasons": None})
    r = score_candidate(cv_strong, jd)
    assert r["breakdown"]["fit"] == pytest.approx(0.0)
    assert isinstance(r["score"], int)


def test_cv_data_loi_tra_ve_error(jd):
    assert "error" in score_candidate({"error": "khong doc duoc PDF"}, jd)
    assert "error" in score_candidate(None, jd)


# ── Nhanh tien loc ──

def test_ho_so_bi_tien_loc_chan_thi_diem_0_va_khong_goi_LLM(jd, fake_llm):
    cv = {
        "name": "Le Van C", "email": "c@x.com", "phone": "", "skills": [],
        "years_experience": 0.0, "education": [], "extraction_ok": True,
        "prefilter_passed": False, "note": "Tien loc tu khoa: CV khong nhac den ...",
    }
    r = score_candidate(cv, jd)
    assert r["score"] == 0
    assert r["hard_filter_passed"] is False
    assert fake_llm.calls == []


def test_ho_so_bi_tien_loc_chi_neu_MOT_ly_do(jd, fake_llm):
    """Khong duoc liet ke 'thieu ky nang/hoc van/kinh nghiem' - cac truong do rong
    vi ta chu dong bo qua LLM, khong phai su that ve ung vien."""
    cv = {
        "name": "", "email": "", "phone": "", "skills": [], "years_experience": 0.0,
        "education": [], "extraction_ok": True, "prefilter_passed": False,
        "note": "Tien loc tu khoa: CV khong nhac den bat ky ky nang bat buoc nao",
    }
    r = score_candidate(cv, jd)
    assert len(r["hard_filter_failures"]) == 1
    assert "Tien loc" in r["hard_filter_failures"][0]
    assert not any("Hoc van" in f for f in r["hard_filter_failures"])


# ── Hieu chuan thang diem (lien quan truc tiep den nguong trong config.py) ──

def test_ho_so_vua_du_tieu_chi_bat_buoc_khong_duoc_invite(jd, cv_strong, fake_llm):
    """Ung vien VUA DU tieu chi bat buoc phai o duoi nguong moi phong van.

    Day la test giu hieu chuan: cac tieu chi BAT BUOC duoc tinh diem MOT LAN NUA o
    buoc diem mem (du required skills = 28/40, dat hoc van toi thieu = 20/20), nen
    ho so vua du tieu chi da co san ~63-73 diem. Voi nguong cu 75 thi nguoi "vua du"
    duoc moi phong van - sai nghiep vu. Xem giai thich trong config.py.
    """
    from config import INVITE_THRESHOLD

    cv_strong["skills"] = ["python", "sql"]                 # dung du required, 0 nice-to-have
    cv_strong["years_experience"] = 2.0                     # dung muc toi thieu
    cv_strong["education"] = [{"degree": "bachelor", "field": "CNTT", "school": "X"}]

    r = score_candidate(cv_strong, jd)
    assert r["hard_filter_passed"] is True                   # van qua loc cung
    assert r["score"] < INVITE_THRESHOLD, (
        f"diem {r['score']} >= nguong invite {INVITE_THRESHOLD} - nguoi VUA DU tieu chi "
        "khong duoc tu dong moi phong van"
    )


def test_san_diem_cua_ho_so_qua_loc_cung(jd, cv_strong, fake_llm):
    """Ghi lai bang so cai san ~63 diem: 28 (skills) + 15 (exp 2/4) + 20 (edu) + 0 (fit)."""
    fake_llm.set({"fit_score": 0.0, "reasons": []})
    cv_strong["skills"] = ["python", "sql"]
    cv_strong["years_experience"] = 2.0
    r = score_candidate(cv_strong, jd)
    assert r["breakdown"]["skills"] == pytest.approx(28.0)
    assert r["breakdown"]["experience"] == pytest.approx(15.0)
    assert r["breakdown"]["education"] == pytest.approx(20.0)
    assert r["score"] == 63
