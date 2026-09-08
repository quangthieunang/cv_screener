"""Test dieu phoi pipeline (graph.py).

Trong tam: nhanh dieu kien sau extract. Neu routing sai, CV scan anh se di vao
score_node va bi cham 0 diem roi TU CHOI - dung ra phai de nguoi xem (manual_review).
Cac test o day khong goi Ollama (chat_json bi thay) va khong ghi ra data/outputs/.
"""
import pytest

from graph import build_graph, route_after_extract, screen_cv
from tests.conftest import CV_TEXT_JUNK, CV_TEXT_OK


# ── Routing ──

def test_extraction_ok_thi_di_cham_diem():
    assert route_after_extract({"cv_data": {"extraction_ok": True}}) == "score"


def test_khong_co_text_thi_bo_qua_cham_diem():
    assert route_after_extract({"cv_data": {"extraction_ok": False}}) == "decide"


def test_thieu_cv_data_thi_mac_dinh_di_cham_diem():
    """extraction_ok vang mat -> coi nhu True (khong tu dong loai vi thieu co)."""
    assert route_after_extract({}) == "score"
    assert route_after_extract({"cv_data": None}) == "score"
    assert route_after_extract({"cv_data": {}}) == "score"


def test_graph_compile_duoc():
    assert build_graph() is not None


# ── Chay tron pipeline ──

@pytest.fixture
def jd_tmp(jd, tmp_path):
    """jd voi ban nhap email ghi vao tmp_path - khong cham data/outputs/."""
    jd["outputs"] = {"email_dir": str(tmp_path / "emails")}
    return jd


def test_ung_vien_manh_di_het_pipeline_ra_invite(make_pdf, jd_tmp, fake_extract_llm,
                                                 fake_llm, tmp_path):
    out = screen_cv(make_pdf("cv.pdf", CV_TEXT_OK), jd_tmp)
    assert out["cv_data"]["extraction_ok"] is True
    assert out["score_result"]["hard_filter_passed"] is True
    assert out["decision"] == "invite"
    assert out["email_result"]["status"] == "draft"
    assert (tmp_path / "emails" / "invite_cv.txt").exists()
    assert out["errors"] == []


def test_ho_so_bi_tien_loc_ra_reject_va_khong_goi_LLM(make_pdf, jd_tmp,
                                                      fake_extract_llm, fake_llm):
    out = screen_cv(make_pdf("junk.pdf", CV_TEXT_JUNK), jd_tmp)
    assert out["decision"] == "reject"
    assert out["cv_data"]["prefilter_passed"] is False
    assert fake_extract_llm.calls == [] and fake_llm.calls == []


def test_cv_scan_anh_ra_manual_review_khong_soan_email(make_pdf, jd_tmp,
                                                       fake_extract_llm, fake_llm):
    out = screen_cv(make_pdf("scan.pdf"), jd_tmp)
    assert out["decision"] == "manual_review"
    assert out["score_result"] is None, "khong duoc cham diem CV chua doc duoc"
    assert out["email_result"]["status"] == "skipped"


def test_pdf_khong_ton_tai_thi_ghi_errors_va_manual_review(jd_tmp, tmp_path,
                                                           fake_extract_llm, fake_llm):
    out = screen_cv(str(tmp_path / "khong_co.pdf"), jd_tmp)
    assert out["decision"] == "manual_review"
    assert out["errors"] and "extract_node" in out["errors"][0]


def test_LLM_boc_tach_loi_thi_manual_review_chu_khong_reject(make_pdf, jd_tmp,
                                                             fake_extract_llm, fake_llm):
    """Loi ha tang khong duoc bien thanh quyet dinh loai ung vien."""
    fake_extract_llm.set({"error": "Ollama khong phan hoi"})
    out = screen_cv(make_pdf("cv.pdf", CV_TEXT_OK), jd_tmp)
    assert out["decision"] == "manual_review"
    assert out["errors"]


def test_state_cuoi_du_moi_khoa_cua_contract(make_pdf, jd_tmp, fake_extract_llm, fake_llm):
    out = screen_cv(make_pdf("cv.pdf", CV_TEXT_OK), jd_tmp)
    for key in ("pdf_path", "jd", "cv_data", "score_result",
                "decision", "email_result", "errors"):
        assert key in out, f"thieu khoa state: {key}"


def test_chay_lai_cung_CV_cho_ket_qua_y_HET(make_pdf, jd_tmp, fake_extract_llm, fake_llm):
    """Cam ket cot loi: diem do Python cong nen khong dao dong giua cac lan chay."""
    path = make_pdf("cv.pdf", CV_TEXT_OK)
    a = screen_cv(path, jd_tmp)
    b = screen_cv(path, jd_tmp)
    assert a["score_result"]["score"] == b["score_result"]["score"]
    assert a["decision"] == b["decision"]
