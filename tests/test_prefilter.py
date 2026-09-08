"""Test tien loc tu khoa (tools/prefilter.py).

Trong tam: bo loc phai CO Y LONG. Moi test o day ton tai de bao ve mot dieu duy nhat -
khong bao gio chan nham mot CV co the phu hop.
"""
from tools.prefilter import keyword_prefilter


# Text du dai de vuot nguong min_text_len (200 ky tu).
FILLER = " kinh nghiem lam viec du an cong ty trach nhiem ky nang phat trien" * 6


def test_cho_qua_khi_co_ky_nang_bat_buoc(jd):
    r = keyword_prefilter("Backend developer, thanh thao Python va Django." + FILLER, jd)
    assert r["passed"] is True
    assert "python" in r["hits"]


def test_loai_khi_khong_co_ky_nang_bat_buoc_nao(jd):
    r = keyword_prefilter("Chuyen vien Marketing: Facebook Ads, Photoshop, SEO." + FILLER, jd)
    assert r["passed"] is False
    assert r["hits"] == []
    assert "python" in r["reason"] and "sql" in r["reason"]


def test_chi_can_MOT_ky_nang_la_du_de_qua(jd):
    """Thieu 'sql' nhung co 'python' -> van cho qua; viec danh gia du/thieu la cua Tool 2."""
    r = keyword_prefilter("Python developer, chua tung dung co so du lieu." + FILLER, jd)
    assert r["passed"] is True
    assert r["hits"] == ["python"]


def test_khong_phan_biet_hoa_thuong(jd):
    r = keyword_prefilter("Senior PYTHON Engineer." + FILLER, jd)
    assert r["passed"] is True


def test_khop_qua_ten_goi_khac(jd):
    """CV chi viet 'PostgreSQL' -> chua 'sql' -> qua. Va alias postgres cung phai qua."""
    jd["mandatory"]["required_skills"] = ["postgresql"]
    r = keyword_prefilter("Database Administrator, 6 nam Postgres va Oracle." + FILLER, jd)
    assert r["passed"] is True
    assert r["hits"] == ["postgresql"]


def test_khop_long_la_co_y(jd):
    """'mysql' chua chuoi 'sql' -> tinh la hit. Sai so chi lam bo loc DE hon, khong chat hon."""
    r = keyword_prefilter("Fullstack PHP, MySQL, jQuery." + FILLER, jd)
    assert r["passed"] is True
    assert r["hits"] == ["sql"]


def test_ky_nang_vat_qua_hai_dong_van_khop(jd):
    """Text PDF hay bi xuong dong giua cac muc - chuan hoa khoang trang phai xu ly duoc."""
    text = "Ky nang:\n  -   Python\n  -   SQL\n" + FILLER
    r = keyword_prefilter(text, jd)
    assert r["passed"] is True
    assert set(r["hits"]) == {"python", "sql"}


def test_text_qua_ngan_luon_cho_qua(jd):
    """CV scan anh / PDF loi -> khong du co so ket luan -> khong duoc tu chan."""
    r = keyword_prefilter("Nguyen Van A", jd)
    assert r["passed"] is True
    assert "qua ngan" in r["reason"]


def test_tat_qua_cau_hinh(jd):
    jd["prefilter"] = {"enabled": False}
    r = keyword_prefilter("Marketing, Photoshop, Facebook Ads." + FILLER, jd)
    assert r["passed"] is True
    assert "bi tat" in r["reason"]


def test_jd_khong_co_ky_nang_bat_buoc_thi_cho_qua(jd):
    jd["mandatory"]["required_skills"] = []
    r = keyword_prefilter("Marketing, Photoshop." + FILLER, jd)
    assert r["passed"] is True


def test_jd_rong_khong_lam_vo(jd):
    assert keyword_prefilter("bat ky noi dung nao", {})["passed"] is True
    assert keyword_prefilter("", None)["passed"] is True


def test_nguong_do_dai_chinh_duoc(jd):
    """Ha min_text_len xuong 0 -> text ngan cung bi do tu khoa."""
    jd["prefilter"] = {"min_text_len": 0}
    assert keyword_prefilter("Marketing", jd)["passed"] is False
    assert keyword_prefilter("Python dev", jd)["passed"] is True
