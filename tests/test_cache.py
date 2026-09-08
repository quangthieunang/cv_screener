"""Test cache boc tach theo hash noi dung PDF (cache.py + tich hop vao Tool 1).

Moi test tro cache vao tmp_path - KHONG test nao duoc doc/ghi data/cache/ that.
Cam ket duoc bao ve: cache dung thi tiet kiem 1 lan goi LLM; cache SAI thi tra ve
du lieu cua nguoi khac -> nen phan lon test o day la ve DUNG KHOA.
"""
import json

import pytest

from cache import ExtractCache, cache_for, reset_registry, text_fingerprint
from tests.conftest import CV_TEXT_JUNK, CV_TEXT_OK
from tools.extract_cv import extract_cv_info


@pytest.fixture
def cached_jd(jd, tmp_path):
    """jd voi cache BAT, tro vao tmp_path."""
    jd["cache"] = {"enabled": True, "path": str(tmp_path / "cache.jsonl")}
    reset_registry()
    return jd


# ── Fingerprint ──

def test_cung_noi_dung_thi_cung_fingerprint():
    assert text_fingerprint(CV_TEXT_OK) == text_fingerprint(CV_TEXT_OK)


def test_noi_dung_khac_thi_fingerprint_khac():
    assert text_fingerprint(CV_TEXT_OK) != text_fingerprint(CV_TEXT_JUNK)


def test_khac_biet_khoang_trang_khong_lam_truot_cache():
    """Bam LOP TEXT chu khong bam byte file: cung mot CV xuat lai tu Word se ra byte
    khac (metadata thoi diem tao) va doi cho xuong dong - khong duoc doi khoa."""
    assert text_fingerprint("Python,  SQL\n\nDocker") == text_fingerprint("Python, SQL Docker")


def test_text_rong_va_None_khong_lam_vo():
    assert text_fingerprint("") == text_fingerprint(None)


# ── ExtractCache ──

def test_ghi_roi_doc_lai_duoc_tu_dia(tmp_path):
    path = tmp_path / "c.jsonl"
    ExtractCache(path=path).put("fp1", {"name": "A", "skills": ["python"]})
    assert ExtractCache(path=path).get("fp1") == {"name": "A", "skills": ["python"]}


def test_dem_hits_va_misses(tmp_path):
    c = ExtractCache(path=tmp_path / "c.jsonl")
    assert c.get("chua_co") is None and c.misses == 1
    c.put("fp1", {"name": "A"})
    assert c.get("fp1") is not None and c.hits == 1


def test_khoa_gom_ca_ten_model(tmp_path):
    """Doi model la doi ket qua boc tach -> khong duoc dung lai ban ghi cua model cu."""
    path = tmp_path / "c.jsonl"
    ExtractCache(path=path, model="model-a").put("fp1", {"name": "A"})
    assert ExtractCache(path=path, model="model-b").get("fp1") is None
    assert ExtractCache(path=path, model="model-a").get("fp1") is not None


def test_khong_cache_ket_qua_loi(tmp_path):
    c = ExtractCache(path=tmp_path / "c.jsonl")
    c.put("fp1", {"error": "LLM that bai"})
    assert c.get("fp1") is None and c.writes == 0


def test_tra_ve_ban_copy_sua_khong_anh_huong_cache(tmp_path):
    c = ExtractCache(path=tmp_path / "c.jsonl")
    c.put("fp1", {"skills": ["python"]})
    got = c.get("fp1")
    got["skills"].append("BI SUA")
    assert c.get("fp1")["skills"] == ["python"]


def test_ghi_de_theo_ban_ghi_moi_nhat(tmp_path):
    path = tmp_path / "c.jsonl"
    c = ExtractCache(path=path)
    c.put("fp1", {"name": "cu"})
    c.put("fp1", {"name": "moi"})
    assert ExtractCache(path=path).get("fp1") == {"name": "moi"}


def test_dong_hong_trong_file_bi_bo_qua_khong_lam_vo(tmp_path):
    """Cache khong bao gio duoc lam vo pipeline - file loi thi coi nhu khong co."""
    path = tmp_path / "c.jsonl"
    path.write_text('{"key": "x", KHONG PHAI JSON\n'
                    + json.dumps({"key": "m:fp1", "cv_data": {"name": "A"}}) + "\n",
                    encoding="utf-8")
    c = ExtractCache(path=path, model="m")
    assert c.get("fp1") == {"name": "A"}


def test_file_cache_chua_ton_tai_thi_khong_loi(tmp_path):
    assert ExtractCache(path=tmp_path / "chua/co/c.jsonl").get("fp1") is None


def test_tat_cache_thi_khong_doc_khong_ghi(tmp_path):
    path = tmp_path / "c.jsonl"
    ExtractCache(path=path).put("fp1", {"name": "A"})
    off = ExtractCache(path=path, enabled=False)
    assert off.get("fp1") is None
    off.put("fp2", {"name": "B"})
    assert off.writes == 0


def test_cache_for_dung_chung_instance_theo_duong_dan(tmp_path):
    jd = {"cache": {"enabled": True, "path": str(tmp_path / "c.jsonl")}}
    assert cache_for(jd) is cache_for(dict(jd)), \
        "phai dung chung bo dem trong ca batch, khong nap lai JSONL cho tung CV"


# ── Tich hop voi Tool 1 ──

def test_lan_hai_khong_goi_LLM_nua(make_pdf, cached_jd, fake_extract_llm):
    path = make_pdf("cv.pdf", CV_TEXT_OK)
    first = extract_cv_info(path, jd=cached_jd)
    assert len(fake_extract_llm.calls) == 1

    reset_registry()                       # gia lap chay lai batch trong tien trinh moi
    second = extract_cv_info(path, jd=cached_jd)
    assert len(fake_extract_llm.calls) == 1, "lan hai phai lay tu cache"
    assert second == first


def test_file_khac_ten_cung_noi_dung_cung_dung_cache(make_pdf, cached_jd, fake_extract_llm):
    extract_cv_info(make_pdf("cv_v1.pdf", CV_TEXT_OK), jd=cached_jd)
    extract_cv_info(make_pdf("cv_v2.pdf", CV_TEXT_OK), jd=cached_jd)
    assert len(fake_extract_llm.calls) == 1


def test_tat_cache_thi_luon_goi_lai_LLM(make_pdf, jd, fake_extract_llm):
    path = make_pdf("cv.pdf", CV_TEXT_OK)
    extract_cv_info(path, jd=jd)           # jd fixture da tat cache
    extract_cv_info(path, jd=jd)
    assert len(fake_extract_llm.calls) == 2


def test_tien_loc_chay_TRUOC_cache(make_pdf, cached_jd, fake_extract_llm):
    """Doi JD thi ho so nao bi chan phai tinh lai theo JD moi, khong lay tu cache cu.

    Lan 1: JD yeu cau python/sql -> CV Marketing bi tien loc chan (khong cache gi).
    Lan 2: JD yeu cau photoshop -> CV do phai duoc cho qua va goi LLM.
    """
    path = make_pdf("junk.pdf", CV_TEXT_JUNK)
    r1 = extract_cv_info(path, jd=cached_jd)
    assert r1["prefilter_passed"] is False and fake_extract_llm.calls == []

    cached_jd["mandatory"]["required_skills"] = ["photoshop"]
    r2 = extract_cv_info(path, jd=cached_jd)
    assert r2["prefilter_passed"] is True
    assert len(fake_extract_llm.calls) == 1


def test_ho_so_bi_tien_loc_khong_duoc_ghi_vao_cache(make_pdf, cached_jd, fake_extract_llm, tmp_path):
    extract_cv_info(make_pdf("junk.pdf", CV_TEXT_JUNK), jd=cached_jd)
    assert cache_for(cached_jd).writes == 0


def test_LLM_loi_thi_khong_ghi_cache(make_pdf, cached_jd, fake_extract_llm):
    fake_extract_llm.set({"error": "Ollama khong phan hoi"})
    r = extract_cv_info(make_pdf("cv.pdf", CV_TEXT_OK), jd=cached_jd)
    assert "error" in r
    assert cache_for(cached_jd).writes == 0
