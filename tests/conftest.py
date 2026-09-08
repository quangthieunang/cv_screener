"""
Cau hinh chung cho bo test.

NGUYEN TAC: KHONG test nao duoc goi Ollama hay ghi ra data/outputs/.
Phan LLM luon bi monkeypatch; phan ghi file luon tro vao tmp_path.
Nho vay `pytest` chay duoc trong vai giay, khong can Ollama dang bat.
"""
import os
import sys

import pytest

# Cho phep import config/state/dedupe/tools tu thu muc goc project.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


@pytest.fixture
def jd():
    """JD mau - tu chua, khong doc data/jd.json de test khong vo khi doi du lieu."""
    return {
        "position": "Backend Engineer (Python)",
        "mandatory": {
            "min_years_experience": 2,
            "required_skills": ["python", "sql"],
            "min_education": "bachelor",
        },
        "nice_to_have_skills": ["docker", "aws", "kubernetes", "fastapi"],
        "expected_years_experience": 4,
        "weights": {"skills": 40, "experience": 30, "education": 20, "fit": 10},
        "thresholds": {"invite": 75, "reject": 50},
        "jd_text": "Tuyen Backend Engineer Python, REST API, PostgreSQL, Docker, AWS.",
        # Tat cache tuong minh: KHONG test nao duoc doc/ghi data/cache/ that.
        # Test cache rieng (test_cache.py) tu tro "path" vao tmp_path.
        "cache": {"enabled": False},
        "prefilter": {"enabled": True},
    }


@pytest.fixture
def cv_strong():
    return {
        "name": "Tran Thi B",
        "email": "b@example.com",
        "phone": "0912345678",
        "skills": ["python", "sql", "docker", "aws", "fastapi"],
        "years_experience": 5.0,
        "education": [{"degree": "bachelor", "field": "CNTT", "school": "BK"}],
        "extraction_ok": True,
        "prefilter_passed": True,
        "name_guessed": False,
    }


@pytest.fixture
def fake_llm(monkeypatch):
    """Thay chat_json trong tools.score bang ham gia, co dem so lan goi.

    Tra ve object co:
        .calls   -> list cac (prompt, system_prompt) da goi
        .set(fn) -> doi hanh vi tra ve
    Dung de khang dinh "khong goi LLM" o cac nhanh tiet kiem chi phi.
    """
    class Recorder:
        def __init__(self):
            self.calls = []
            self._response = {"fit_score": 1.0, "reasons": ["rat phu hop"]}

        def set(self, response):
            self._response = response

        def __call__(self, prompt, system_prompt="", schema_hint=""):
            self.calls.append((prompt, system_prompt))
            return self._response

    rec = Recorder()
    monkeypatch.setattr("tools.score.chat_json", rec)
    return rec


# ── Tien ich tao PDF that (khong can file mau commit vao repo) ──

def _new_pdf(path, text=None):
    """Tao mot PDF that tai `path`.

    text=None -> PDF CHI CO ANH, khong co lop text: dung mo phong CV scan anh de
    kiem chung nhanh manual_review that su chay (truoc day nhanh nay khong co mau
    nao de thu). Dung ASCII cho text vi font base-14 cua PDF khong co dau tieng Viet.
    """
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    if text is None:
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 120, 120))
        pix.clear_with(200)
        page.insert_image(fitz.Rect(50, 50, 170, 170), pixmap=pix)
    else:
        y = 72
        for line in text.splitlines():
            page.insert_text((60, y), line, fontsize=10)
            y += 14
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def make_pdf(tmp_path):
    """Factory: make_pdf("ten.pdf", "noi dung") -> duong dan PDF that trong tmp_path."""
    def _make(name, text=None):
        return _new_pdf(tmp_path / name, text)
    return _make


CV_TEXT_OK = """TRAN THI B
Backend Engineer
Email: b@example.com
Phone: 0912 345 678
Ky nang: Python, SQL, Docker, AWS, FastAPI
Kinh nghiem: 5 nam phat trien REST API
Hoc van: Cu nhan Cong nghe thong tin - DH Bach Khoa
"""

CV_TEXT_JUNK = """LE VAN C
Chuyen vien Marketing
Email: c@example.com
Phone: 0987654321
Ky nang: Facebook Ads, Photoshop, SEO, Content
Kinh nghiem: 4 nam chay quang cao va quan ly fanpage cho nhieu nhan hang
Hoc van: Cu nhan Marketing - Dai hoc Kinh te Quoc dan
"""


@pytest.fixture
def fake_extract_llm(monkeypatch):
    """Thay chat_json trong tools.extract_cv, dem so lan goi (de test cache/tien loc)."""
    class Recorder:
        def __init__(self):
            self.calls = []
            self._response = {
                "name": "Tran Thi B", "email": "b@example.com", "phone": "0912345678",
                "skills": ["Python", "SQL", "Docker"], "years_experience": 5,
                "education": [{"degree": "bachelor", "field": "CNTT", "school": "BK"}],
            }

        def set(self, response):
            self._response = response

        def __call__(self, prompt, system_prompt="", schema_hint=""):
            self.calls.append((prompt, system_prompt))
            return self._response

    rec = Recorder()
    monkeypatch.setattr("tools.extract_cv.chat_json", rec)
    return rec


@pytest.fixture(autouse=True)
def _clean_cache_registry():
    """Moi test bat dau voi registry cache sach (cache.py memo theo duong dan)."""
    import cache
    cache.reset_registry()
    yield
    cache.reset_registry()
