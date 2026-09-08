"""Test chong trung ung vien (dedupe.py).

Trong tam: hai hong hoc doi lap nhau.
  1. KHONG gop nguoi khac nhau chi vi trung ho ten (ho ten Viet Nam trung rat pho bien)
     -> gop nham se lam mot nguoi that bi mat khoi bang xep hang.
  2. PHAI gop khi cung email/sdt -> khong gop se gui HAI email cho cung mot dia chi,
     thoi khi mot cai la "moi phong van" va cai kia la "tu choi".
"""
from dedupe import dedupe_candidates, normalize_email, normalize_name, normalize_phone


def _rec(file, name="", email="", phone="", score=0):
    return {"file": file, "name": name, "email": email, "phone": phone, "score": score}


# ── Chuan hoa ──

def test_chuan_hoa_email_bo_khoang_trang_va_ha_chu_thuong():
    assert normalize_email(" B@X.COM ") == "b@x.com"
    assert normalize_email(None) == ""


def test_chuan_hoa_phone_lay_9_so_cuoi():
    """'+84912345678', '0912345678', '912345678' phai ve cung mot khoa."""
    assert normalize_phone("+84912345678") == normalize_phone("0912345678") \
        == normalize_phone("912 345 678") == "912345678"


def test_chuan_hoa_phone_qua_ngan_thi_khong_tin_cay():
    assert normalize_phone("12345") == ""
    assert normalize_phone("") == ""


def test_chuan_hoa_ten_bo_dau_tieng_viet():
    assert normalize_name("Nguyễn Văn A") == "nguyen van a"
    assert normalize_name("  Trần   Thị  B ") == "tran thi b"
    assert normalize_name("Đỗ Đình Đ") == "do dinh d"


# ── Gop theo khoa manh ──

def test_gop_khi_trung_email_khong_phan_biet_hoa_thuong():
    recs = [_rec("a.pdf", "Tran Thi B", "b@x.com", score=70),
            _rec("b.pdf", "Tran Thi B", "B@X.COM", score=84)]
    stats = dedupe_candidates(recs)
    assert stats["duplicates_marked"] == 1
    assert len(stats["groups"]) == 1


def test_ban_chinh_la_ban_co_diem_cao_nhat():
    recs = [_rec("thap.pdf", "A", "a@x.com", score=60),
            _rec("cao.pdf", "A", "a@x.com", score=90)]
    dedupe_candidates(recs)
    cao = next(r for r in recs if r["file"] == "cao.pdf")
    thap = next(r for r in recs if r["file"] == "thap.pdf")
    assert cao["duplicate_of"] is None and cao["duplicate_count"] == 1
    assert thap["duplicate_of"] == "cao.pdf"


def test_hoa_diem_thi_chon_file_dung_truoc_cho_on_dinh():
    """Ket qua phai tat dinh - chay lai khong duoc doi ban chinh."""
    recs = [_rec("b.pdf", "A", "a@x.com", score=70), _rec("a.pdf", "A", "a@x.com", score=70)]
    dedupe_candidates(recs)
    assert next(r for r in recs if r["file"] == "a.pdf")["duplicate_of"] is None


def test_gop_theo_so_dien_thoai_khi_email_khac_nhau():
    recs = [_rec("a.pdf", "A", "a1@x.com", "0912345678", score=70),
            _rec("b.pdf", "A", "a2@x.com", "+84912345678", score=60)]
    stats = dedupe_candidates(recs)
    assert stats["duplicates_marked"] == 1


def test_gop_bac_cau_qua_email_va_phone():
    """A trung B qua email, B trung C qua phone -> ca ba mot nhom."""
    recs = [_rec("a.pdf", "A", "same@x.com", "0900000001", score=50),
            _rec("b.pdf", "A", "same@x.com", "0900000002", score=90),
            _rec("c.pdf", "A", "other@x.com", "0900000002", score=60)]
    stats = dedupe_candidates(recs)
    assert len(stats["groups"]) == 1
    assert stats["duplicates_marked"] == 2
    assert next(r for r in recs if r["file"] == "b.pdf")["duplicate_of"] is None


# ── KHONG gop chi vi trung ten ──

def test_trung_ho_ten_thi_chi_NGHI_NGO_khong_gop():
    """Hai nguoi khac nhau trung ho ten: phai giu ca hai trong xep hang."""
    recs = [_rec("a.pdf", "Nguyen Van A", "a1@x.com", "0900000001", score=80),
            _rec("b.pdf", "Nguyễn Văn A", "a2@x.com", "0900000002", score=75)]
    stats = dedupe_candidates(recs)
    assert stats["duplicates_marked"] == 0
    assert stats["groups"] == []
    assert len(stats["suspects"]) == 1
    assert all(r["duplicate_of"] is None for r in recs)


def test_da_gop_boi_khoa_manh_thi_khong_bao_nghi_ngo_nua():
    recs = [_rec("a.pdf", "Nguyen Van A", "a@x.com", score=80),
            _rec("b.pdf", "Nguyen Van A", "a@x.com", score=75)]
    stats = dedupe_candidates(recs)
    assert stats["suspects"] == []


def test_ban_ghi_thieu_email_va_phone_khong_bi_gop_voi_nhau():
    """Nhieu CV khong boc tach duoc lien lac -> khong duoc coi la cung mot nguoi."""
    recs = [_rec("a.pdf", "X"), _rec("b.pdf", "Y"), _rec("c.pdf", "Z")]
    stats = dedupe_candidates(recs)
    assert stats["duplicates_marked"] == 0


# ── Ca bien ──

def test_danh_sach_rong_va_mot_phan_tu():
    assert dedupe_candidates([])["duplicates_marked"] == 0
    assert dedupe_candidates([_rec("a.pdf", "A", "a@x.com")])["groups"] == []


def test_khong_xoa_ban_ghi_nao():
    """HR van phai thay day du moi ho so trong bao cao - chi buoc gui email moi bo qua."""
    recs = [_rec(f"{i}.pdf", "A", "a@x.com", score=i) for i in range(5)]
    dedupe_candidates(recs)
    assert len(recs) == 5
