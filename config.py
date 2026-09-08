"""
Module cau hinh tap trung cho cv-screener (HR CV Screener Agent).

Gom hang so LLM + duong dan + nguong.
SMTP doc tu bien moi truong (.env) de gui email that - KHONG hardcode mat khau.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# ── LLM (Ollama local) ──
MODEL_NAME = 'qwen2.5:7b'
OLLAMA_HOST = 'http://localhost:11434'
MAX_RETRIES = 2
TEMPERATURE = 0

# ── Duong dan ──
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
CVS_DIR = DATA_DIR / 'cvs'
OUTPUTS_DIR = DATA_DIR / 'outputs'
EMAIL_DIR = OUTPUTS_DIR / 'emails'
JD_PATH = DATA_DIR / 'jd.json'
CACHE_DIR = DATA_DIR / 'cache'
EXTRACT_CACHE_PATH = CACHE_DIR / 'extract_cache.jsonl'

# ── Nguong quyet dinh mac dinh (jd.json co the ghi de qua khoa "thresholds") ──
#
# HIEU CHUAN - doc ky truoc khi doi:
#   Ho so DA QUA loc cung khong bao gio bat dau tu 0 diem, vi cac tieu chi bat buoc
#   duoc tinh diem MOT LAN NUA o buoc diem mem: du 100% ky nang bat buoc = 0.7x40 = 28,
#   dat hoc van toi thieu = 20/20, va it nhat 50% so nam mong doi = 15/30.
#   => SAN diem thuc te cua nguoi qua loc cung la ~63, khong phai 0.
#
#   Vi vay nguong PHAI nam trong dai 63-100. Voi nguong cu 75/50, moi ho so vua du
#   tieu chi bat buoc da duoc ~78 diem -> "invite", va nhanh "reject vi diem thap"
#   khong bao gio chay (khong ai qua loc cung ma duoi 50). Xem tests/test_score.py::
#   test_ho_so_vua_du_tieu_chi_bat_buoc_khong_duoc_invite - test do giu hieu chuan nay.
INVITE_THRESHOLD = 85   # >= : moi phong van
REJECT_THRESHOLD = 70   # [REJECT, INVITE) : giu lai (hold); < REJECT : tu choi

# ── Bac hoc van chuan hoa (thap -> cao). Dung chung boi extract_cv & score. ──
DEGREE_LEVELS = ["highschool", "college", "bachelor", "master", "phd"]

# Trong so mac dinh khi jd.json khong khai bao "weights".
DEFAULT_WEIGHTS = {"skills": 40, "experience": 30, "education": 20, "fit": 10}

# ── Email / SMTP ──
# Nap .env neu co (nam cung thu muc project). Khong bat buoc phai co khi chi dry-run.
load_dotenv(BASE_DIR / '.env')

# Mac dinh KHONG gui that: chi soan nhap. main.py --send se tat co nay.
EMAIL_DRY_RUN = True

SMTP_HOST = os.getenv('SMTP_HOST', '')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASS = os.getenv('SMTP_PASS', '')
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER)
