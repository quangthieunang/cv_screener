# HR CV Screener Agent

Trợ lý lọc hồ sơ tuyển dụng: tự động **bóc tách thông tin CV (PDF)**, **chấm điểm mức độ
phù hợp với JD (thang 1-100)**, và **ra quyết định mời phỏng vấn / từ chối** kèm soạn email.
Xử lý được hàng loạt cả thư mục CV — giải bài toán "500 CV, 80% không đạt yêu cầu cơ bản".

Xây trên nền **LangGraph pipeline tất định** + **Ollama `qwen2.5:7b` (local)**, cùng phong cách
với `shopping-agent` và `ReAct demo` trong cùng lab.

**Đo được:** 500 CV ≈ **18 phút** (chạy lại ≈ 8 phút nhờ cache), trung bình **2,16s/CV**,
tiết kiệm **80%** số lần gọi LLM. Bộ test 183 case chạy 1,2s không cần Ollama.
Chi tiết thiết kế và số liệu: [DESIGN.md](DESIGN.md).

---

## Kiến trúc

Mỗi lần chạy pipeline xử lý **một ứng viên**; `main.py` lặp qua cả thư mục để chạy hàng loạt.

```
START -> extract -> (extraction_ok?) -> score -> decide -> END
                         └── (CV scan ảnh, không có text) ──> decide (manual_review)
```

3 công cụ (tools) — đúng như đề bài:

| Tool | File | Nhiệm vụ |
|------|------|----------|
| 1. `extract_cv_info(pdf_file, jd)` | `tools/extract_cv.py` | Đọc PDF (PyMuPDF) → LLM bóc tách: kỹ năng, số năm KN, học vấn, tên/email/SĐT |
| 2. `score_candidate(cv_data, jd)` | `tools/score.py` | **Hybrid**: lọc cứng (tiêu chí bắt buộc) + điểm mềm có trọng số + LLM đánh giá "fit" |
| 3. `send_hr_email(candidate, action)` | `tools/email_tool.py` | Soạn (và tùy chọn gửi thật qua SMTP) email mời PV / từ chối |

Cùng 3 module hỗ trợ:

| Module | File | Nhiệm vụ |
|--------|------|----------|
| Tiền lọc từ khoá | `tools/prefilter.py` | Chặn hồ sơ không nhắc tới kỹ năng bắt buộc nào — **trước** khi tốn lần gọi LLM |
| Cache bóc tách | `cache.py` | Hash lớp text CV → chạy lại batch không gọi lại LLM |
| Chống trùng ứng viên | `dedupe.py` | Gộp hồ sơ cùng email/SĐT; trùng họ tên chỉ cảnh báo |

Điều phối: `graph.py` (LangGraph) + `nodes/*.py` (mỗi node bọc 1 tool).
Trạng thái & giao kèo JSON giữa các bước: xem `state.py`.

### 4 lớp lọc theo thứ tự chi phí
`đọc PDF (~0) → tiền lọc từ khoá (~0) → cache (~0) → gọi LLM (đắt)`.
Đo thực tế: **80% hồ sơ không bao giờ chạm tới LLM**, và chạy lại batch thì **100%** không chạm.
Vì 99% thời gian nằm trong LLM, mọi tối ưu chỉ có nghĩa nếu nó cắt bớt lời gọi LLM.

### Cách chấm điểm Hybrid
- **Lọc cứng (Python, chạy trước):** thiếu số năm KN / kỹ năng bắt buộc / học vấn tối thiểu
  → tự loại (`hard_filter_passed=false`), **bỏ qua bước LLM tốn kém**.
- **Điểm mềm (chỉ khi qua lọc cứng):** tổng hợp có trọng số 4 thành phần
  `skills / experience / education / fit`. Ba phần đầu Python tính (ổn định); riêng `fit` gọi
  LLM đánh giá định tính. **Con số 1-100 cuối cùng do Python cộng lại** → không dao động giữa các lần chạy.
- **Chống thiên vị:** prompt chấm `fit` chỉ nhận `skills / years_experience / education` —
  không có tên, giới tính, tuổi, trường học cụ thể.

### Quyết định
`hard_filter_passed=false` → **reject** · `score ≥ invite` → **invite** ·
`reject ≤ score < invite` → **hold** · còn lại → **reject** ·
CV không có text → **manual_review**. Ngưỡng mặc định: **invite 85 / reject 70** (JD ghi đè được).

> **Vì sao 85/70 chứ không phải 75/50?** Hồ sơ đã qua lọc cứng có **sàn ~63 điểm**, vì các tiêu
> chí bắt buộc được tính điểm một lần nữa ở bước điểm mềm (đủ required skills = 28/40, đạt học
> vấn tối thiểu = 20/20). Dải điểm thật là 63-100, nên ngưỡng phải nằm trong dải đó — nếu không,
> người *vừa đủ* tiêu chí sẽ được tự động mời phỏng vấn. Giải thích đầy đủ: [DESIGN.md §6](DESIGN.md).

---

## Cài đặt

Yêu cầu: **CPython từ python.org** (khuyến nghị 3.13; tránh conda/MSYS2) và **Ollama** đang chạy.

```bash
# 1) Tạo môi trường ảo + cài thư viện
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt

# 2) Kéo model (nếu chưa có)
ollama pull qwen2.5:7b
```

Thư viện: `langgraph`, `ollama`, `pymupdf`, `python-dotenv` (+ `pytest` để chạy test).

---

## Sử dụng

```bash
# Chấm điểm cả thư mục data/cvs/ theo data/jd.json (dry-run: chỉ soạn email nháp)
python main.py

# Chỉ xử lý 3 hồ sơ đầu (để thử nhanh)
python main.py --limit 3

# Chỉ định JD / thư mục CV / thư mục xuất khác
python main.py --jd data/jd.json --cvs data/cvs --out data/outputs

# GỬI EMAIL THẬT qua SMTP (sẽ hỏi xác nhận trước khi gửi)
python main.py --send
```

Các cờ tắt từng lớp tối ưu (dùng khi cần đối chiếu hoặc gỡ lỗi):

| Cờ | Tác dụng |
|---|---|
| `--no-prefilter` | Tắt tiền lọc từ khoá → gọi LLM bóc tách cho **mọi** hồ sơ |
| `--no-cache` | Tắt cache → luôn gọi lại LLM dù đã bóc tách hồ sơ đó |
| `--no-dedupe` | Tắt chống trùng ứng viên |

**Đầu vào:** bỏ các file PDF CV vào `data/cvs/`, chỉnh `data/jd.json` (vị trí, tiêu chí
bắt buộc, trọng số, ngưỡng, bật/tắt tiền lọc & cache).

**Đầu ra** (trong thư mục `--out`, mặc định `data/outputs/`):
- `report_ranked.md` — bảng xếp hạng (điểm, quyết định, kỹ năng khớp/thiếu, lý do loại,
  nhóm hồ sơ trùng người, cảnh báo trùng họ tên).
- `candidates.json` — dữ liệu chi tiết từng ứng viên.
- `emails/*.txt` — bản nháp email cho mỗi quyết định invite/reject (đặt tên theo **tên file CV**
  để hai ứng viên trùng họ tên không ghi đè nhau).
- `sent_log.json` — chỉ khi chạy `--send`.

Cache nằm ở `data/cache/extract_cache.jsonl` (JSONL append-only, xoá được bất cứ lúc nào).

---

## Gửi email thật (SMTP)

1. Copy `.env.example` → `.env`, điền thông tin SMTP (Gmail: bật *App password*).
   Mật khẩu **chỉ nằm trong `.env`** — không hardcode, không commit.
2. Chạy `python main.py --send`. Agent in tóm tắt + danh sách người nhận rồi **hỏi xác nhận
   (y/N)** — chỉ gửi khi bạn gõ `y`. Nhật ký ghi ở `data/outputs/sent_log.json`.

> Mặc định luôn là **dry-run** (chỉ soạn nháp). Việc gửi thật chỉ xảy ra khi có cờ `--send`
> và bạn xác nhận trực tiếp trong terminal.

---

## An toàn (đã tích hợp)
- **Chống prompt-injection:** nội dung CV được xử lý như *dữ liệu*, không phải mệnh lệnh.
  LLM được chỉ thị bỏ qua mọi câu chữ trong CV cố điều khiển điểm/quyết định. Điểm cuối cùng
  do Python cộng nên LLM không thể tự nâng.
- **Email:** mặc định dry-run; gửi thật cần `--send` + xác nhận. Người nhận chỉ lấy từ email
  đã bóc tách trong CV. Email sai định dạng → `status=skipped`, **không** chạm SMTP.
- **Không gọi sai tên:** hồ sơ bị tiền lọc chặn chưa qua LLM nên tên chỉ là phỏng đoán
  (`name_guessed=true`) — email lùi về xưng hô "anh/chị ứng viên", báo cáo gắn nhãn cần kiểm tra.
- **Một người nhận đúng một email:** `dedupe.py` gộp hồ sơ trùng email/SĐT; bước gửi bỏ qua
  bản trùng. Trùng **họ tên** thì chỉ cảnh báo, không gộp (họ tên Việt Nam trùng nhau rất phổ biến).
- **CV scan ảnh (không có lớp text):** gắn cờ `manual_review`, không tự động loại/mời.
  (OCR là hướng mở rộng, ngoài phạm vi hiện tại.)
- **PII không rời máy:** LLM chạy local qua Ollama.

---

## Kiểm thử

**Bộ test tự động** — 183 test, ~1,2s, **không cần Ollama** (mọi lời gọi LLM bị monkeypatch,
mọi ghi file trỏ vào `tmp_path`):

```bash
pytest
```

**Smoke test từng phần** (mỗi module chạy được độc lập):

```bash
python tools/prefilter.py                                      # tiền lọc — 4 case
python tools/extract_cv.py data/cvs/cv_strong_tran_thi_b.pdf   # Tool 1
python tools/score.py                                          # Tool 2 — 3 case mock
python tools/email_tool.py                                     # Tool 3 — nháp invite/reject
python cache.py                                                # cache — ghi/đọc/tắt
python dedupe.py                                               # chống trùng — 5 bản ghi
python graph.py                                                # pipeline 1 ứng viên
python main.py                                                 # batch dry-run
```

**Đo hiệu năng:**

```bash
python benchmark.py --n 500 --mock-llm     # throughput trần, không cần Ollama
python benchmark.py --n 25 --warm          # số liệu thật + hiệu quả cache
```

Benchmark sinh CV giả lập trong thư mục tạm và tự xoá — không để lại rác.

**Nghiệm thu** với 3 CV mẫu: `cv_strong → invite (96)`, `cv_mid → hold (78)`,
`cv_weak → reject (0, bị tiền lọc chặn)`; sinh đúng 2 bản nháp email, không sinh cho `hold`.

## Cấu trúc thư mục
```
cv-screener/
├── config.py      state.py      llm.py      graph.py     main.py
├── cache.py       dedupe.py     benchmark.py
├── tools/         prefilter.py  extract_cv.py  score.py   email_tool.py
├── nodes/         extract_node.py  score_node.py  decide_node.py
├── tests/         conftest.py   test_prefilter.py  test_extract.py  test_score.py
│                  test_decide.py  test_email.py   test_cache.py    test_dedupe.py
│                  test_graph.py   test_main.py
├── data/          jd.json       cvs/        outputs/     cache/
├── requirements.txt  .env.example  .gitignore  DESIGN.md
```
