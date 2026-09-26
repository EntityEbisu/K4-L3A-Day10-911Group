# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4          |
| Tên nhóm         | 911Group    |
| Repository         | https://github.com/EntityEbisu/K4-L3A-Day10-911Group |
| Ngày hoàn thành | 2026-09-25  |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Trọng Minh | 2A202602496 | Trưởng nhóm / Pipeline Integrator (custom API, orchestration) | `core/config.py`, `retrieval/embeddings.py`, `retrieval/llm.py`, `retrieval/index.py`, `pipelines/phase1.py`, `pipelines/corruption_flow.py`, `.env.example` |
| 2 | Dương Minh Hiếu | 2A202602488 | Data Ingestion & Cleaning Owner (raw preservation, quality gate) | `ingestion/crossref.py` (dual-mode fetch), `ingestion/cleaning.py` (`age_days`, `text_for_embedding`), `observability/quality.py` (GX 1.x, Freshness SLA) |
| 3 | Lê Mạnh Cường | 2A202602604 | Pipeline & Observability Engineer (corruption, repair, reporting) | `ingestion/corruption.py` (6 kịch bản), `observability/reporting.py` (3-state report), `evaluation/testset.py` (10 TV questions), `pipelines/corruption_flow.py` |

---

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành toàn bộ **7-layer Data Pipeline & Observability lab** theo dev_plan.md:

1. **Raw Preservation (Crossref Ingestion):** Lấy thành công 24 bài báo khoa học từ Crossref REST API với cơ chế fallback offline (`refresh_source=False` → dùng snapshot), dual-mode retry 429/503.
2. **Data Cleaning & Modeling:** Chuẩn hóa schema (JATS strip, `age_days`, `text_for_embedding` 5 dòng), khử trùng lặp theo `paper_id`, 24 bản ghi sạch.
3. **Quality Gate (GX 1.x + Freshness SLA):** 6 expectations (row count, null check, unique key, min length) + freshness SLA (age_days>180, stale_ratio≤0.25); baseline đạt 6/6 PASS.
4. **Vector Index (custom API):** Embed via POST `/v1/embeddings` (bge-m3 1024-dim) từ `CUSTOM_LLM_BASE_URL=http://127.0.0.1:1234/v1`, 3 ChromaDB collections (baseline/corrupted/repaired, cosine).
5. **Evaluation Baseline:** 10 câu hỏi TV (tóm tắt/tác giả/xuất bản/lĩnh vực round-robin), retrieval_hit_rate=1.0, mean_token_f1=0.8, judge_accuracy=0.7.
6. **Controlled Corruption:** 6 kịch bản deterministic (drop 5 / blank 3 / noise 3 / truncate 3 / stale 5 / duplicate 2) → corrupted hit_rate 0.8, F1 0.6, quality 4/6 FAIL (Silent Failure).
7. **Idempotent Repair & 3-State Comparison:** Phục hồi từ raw snapshot idempotent → repaired hit_rate 1.0, F1 0.8, quality 6/6 PASS → báo cáo corruption_report.md 3 cột chứng minh phục hồi hoàn toàn.

**Blocker chính đã xử lý:** Custom API require Bearer token (phase1.py probe); import mismatch `build_embeddings`/`MiniLMEmbeddings` (alias + re-export); Windows `cp1252` encoding (PYTHONIOENCODING=utf-8); GX 1.x NaN → JSON conversion.

---

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref REST API (dual-mode: refresh_source flag)
    ↓
raw response/records (crossref_response.json, crossref_records.json)
    ↓
parsing: strip JATS, fallback published chain, normalize authors/categories
    ↓
cleaned dataframe (24 × 16 columns: paper_id, title, summary, ..., text_for_embedding, age_days)
    ↓
embedding: POST /v1/embeddings (bge-m3 1024-dim custom API)
    ↓
ChromaDB 3 collections (papers-baseline/corrupted/repaired, cosine)
    ↓
evaluation: 10 TV test set, retrieval_hit_rate + mean_token_f1 + judge_accuracy
    ↓
baseline metrics (hit 1.0, F1 0.8, judge 0.7)
    ↓
corruption: 6 kịch bản → 21 rows, hit 0.8, quality 4/6 FAIL
    ↓
repair: load raw → build_clean idempotent → 24 rows, hit 1.0, quality 6/6 PASS
    ↓
comparison report (3 trạng thái so sánh)
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref API or snapshot | Fetch dual-mode, JATS strip, parse published fallback | `data/raw/*` (2 files, 24 records) | Hiếu |
| Cleaning          | 24 raw records | `age_days`, `text_for_embedding` 5-dòng, dedup, sort | `data/clean/*` (6 files, 3 states) | Hiếu |
| Quality Gate      | Clean DataFrame | GX 1.x 6 expectations, freshness SLA | `data/quality/*` (6 JSON reports) | Hiếu |
| Embedding/Index   | `text_for_embedding` | POST `/v1/embeddings` (custom API bge-m3), ChromaDB cosine | `data/embeddings/*` (3 manifests) | Minh |
| Evaluation        | Test set + index | Retrieval top-k, token F1, LLM judge | `data/results/*_metrics.json` | Cường |
| Corruption        | Clean DataFrame | 6 deterministic kịch bản, rời nhau | `data/clean/*_corrupted.*`, corruption_log.json | Cường |
| Repair            | Raw snapshot + corrupted | Load raw → `build_clean` idempotent | `data/clean/*_repaired.*` | Minh + Cường |
| Orchestration     | Settings | phase1.py (8 bước), corruption_flow.py (repair+compare) | Reports/metrics | Minh |

---

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `custom`         |
| `LLM_MODEL`                | `ternary-bonsai-8b` |
| Embedding model              | `text-embedding-bge-m3` |
| `CUSTOM_LLM_BASE_URL`     | `http://127.0.0.1:1234/v1` |
| Số lượng Crossref records | 24 |
| Retrieval `top_k`           | 4 |
| Freshness threshold          | 180 days, ratio ≤ 0.25 |
| Test set size              | 10 questions (TV) |
| Corruption types           | 6 (drop, blank, noise, truncate, stale, duplicate) |

### Lệnh cài đặt

```bash
uv sync
```

Hoặc với pip:

```bash
python -m pip install -e .
```

### Lệnh chạy

**Baseline (Phase 1):**

```bash
PYTHONPATH=./src PYTHONIOENCODING=utf-8 python script/run_phase1.py
```

**Corruption → Repair → Comparison (Phase 2):**

```bash
PYTHONPATH=./src PYTHONIOENCODING=utf-8 python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | ✅ Thành công | 2026-09-25 | `data/results/baseline_metrics.json` (hit 1.0, F1 0.8, judge 0.7) |
| Corruption flow   | ✅ Thành công | 2026-09-25 | `data/reports/corruption_report.md` (3 cột, corrupted hit 0.8, repaired hit 1.0) |

---

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API (dual-mode snapshot) |
| Query                | `agentic retrieval augmented generation large language model` |
| Filter                | `from-pub-date:2023-03-28,has-abstract:true` (180 ngày) |
| Thời điểm lấy dữ liệu | 2026-09-25 |
| Số record nhận được    | 24 |
| Cơ chế retry/backoff      | 3 lần, sleep 2^attempt, mã 429/503, fallback snapshot offline |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` | string (DOI normalized) | Có | Khóa duy nhất | Loại bản ghi |
| `title` | string | Có | Tiêu đề | Loại bản ghi |
| `summary` | string | Có | Tóm tắt (≥30 ký tự) | Loại nếu < 30, strip JATS XML |
| `authors` | string list | Không | Danh sách tác giả | Gộp thành `authors_joined` |
| `categories` | string list | Không | Lĩnh vực/chuyên ngành | Gộp thành `categories_joined` |
| `published` | ISO 8601 date | Có | Ngày xuất bản | Fallback chain: issued → published → published-print → published-online → created |
| `age_days` | int | Có (derived) | `(run_date - published).days` | Tính toán an toàn múi giờ |
| `text_for_embedding` | string 5-block | Có | `Title / Authors / Published / Categories / Summary` | Dựng từ các trường khác |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Strip JATS XML tags (`<jats:...>`) | Completeness | 24 | `data/clean/papers_clean.json` mỗi dòng không có `<jats:` |
| Standardize published date (ISO 8601) | Validity | 24 | Kiểm tra format `YYYY-MM-DD` |
| Deduplicate by `paper_id` keep first | Uniqueness | 0 (24 unique) | `len(df.paper_id.unique()) == 24` |
| Calculate `age_days` safely | Completeness | 24 | `age_days` column không null |
| Build `text_for_embedding` 5-dòng | Semantic consistency | 24 | Kiểm tra structure Title/Authors/Published/Categories/Summary |

**`text_for_embedding` template:**

```text
Title: <Tiêu đề>
Authors: <Danh sách tác giả được chuẩn hóa>
Published: <YYYY-MM-DD>
Categories: <Lĩnh vực/Chuyên ngành>
Summary: <Tóm tắt, đã strip JATS, ≥30 ký tự>
```

**Document ID:** `paper_id` (DOI normalized: lowercase, no `https://doi.org/` prefix)

**`age_days` calculation:** `(run_date - published_dt).days` sử dụng `datetime.date` (không timestamp) để tránh lệch múi giờ.

---

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 10 |
| `question_type`                        | `tóm tắt`, `tác giả`, `xuất bản`, `lĩnh vực` (round-robin) |
| Ground-truth document ID                 | `paper_id` của tài liệu chứa đáp án |
| Ground-truth answer                      | Câu đầu của `summary` (for `tóm tắt`), hoặc `authors_joined`/`published`/`categories_joined` (for other types) |
| Embedding model                          | `text-embedding-bge-m3` (custom API, 1024-dim) |
| Vector store/collection                  | ChromaDB `papers-baseline`, `papers-corrupted`, `papers-repaired` (cosine) |
| Retrieval `top_k`                       | 4 |
| LLM provider/model                       | `ternary-bonsai-8b` (custom API, Vietnamese output) |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (10 questions, deterministic sort + round-robin) |

**Vì sao test set được giữ nguyên qua 3 trạng thái?**

Để đảm bảo controlled experiment: chỉ biến `data` đổi, `test set` giữ cố định. Nếu mỗi trạng thái sinh test set mới, chênh lệch metric có thể do câu hỏi khác nhau (dễ/khó), không quy được về chất lượng dữ liệu. `phase1.py` chỉ refresh khi `REFRESH_TEST_SET=1` hoặc câu hỏi đầu không phải TV; `corruption_flow.py` tái sử dụng `data/eval/test_set.json` nguyên vẹn.

---

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | ✅ Có | 24 records, 2 files |
| Cleaned dataset          | `data/clean/papers_clean.csv`, `.json` | ✅ Có | 24 × 16 columns |
| Embedding manifest/index | `data/embeddings/papers_embeddings.json` | ✅ Có | backend=custom-openai-compatible |
| Evaluation set           | `data/eval/test_set.json` | ✅ Có | 10 Vietnamese questions |
| Baseline metrics         | `data/results/baseline_metrics.json` | ✅ Có | hit 1.0, F1 0.8, judge 0.7 |
| Quality/freshness        | `data/quality/baseline_quality_report.json`, `freshness_report.json` | ✅ Có | 6/6 PASS, is_fresh=True |
| Baseline report          | `data/reports/phase1_report.md` | ✅ Có | Vietnamese header |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` |          1.0000 | 100% câu hỏi có tài liệu đúng trong top-4 |
| `mean_token_f1`      |          0.8000 | Trung bình F1 token 80% độ trùng khớp |
| `judge_accuracy`     |          0.7000 | LLM judge đánh giá đúng 7/10 câu |
| `mean_judge_score`   |          4.0000 | Điểm trung bình LLM 1–5 thang |

---

## 8. Data quality và freshness

### Quality checks

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| Row count    | Completeness | [5, 5000] | 24 rows ✅ PASS | `data/quality/baseline_quality_report.json` |
| `paper_id` not null | Completeness | 100% non-null | 24/24 ✅ PASS | |
| `title` not null | Completeness | 100% non-null | 24/24 ✅ PASS | |
| `text_for_embedding` not null | Completeness | 100% non-null | 24/24 ✅ PASS | |
| `paper_id` unique | Uniqueness | 100% unique | 24 unique IDs ✅ PASS | |
| `summary` min length (≥30) | Validity | min 30 chars | all ≥30 ✅ PASS | |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | Baseline cleaned dataset (`data/clean/papers_clean.json`) |
| Timestamp mới nhất       | 2026-09-15 |
| Timestamp lâu nhất       | 2026-04-01 |
| Ngưỡng freshness         | age_days > 180 → stale; stale_ratio ≤ 0.25 → is_fresh=True |
| Trạng thái baseline      | ✅ Fresh (`is_fresh=True`) |
| Stale rows / total       | 0/24 = 0% |
| Lý do                     | Toàn bộ 24 bài báo được xuất bản trong 180 ngày gần nhất |

---

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| Drop latest 5 (20%) | `df.drop_duplicates(...).head(5)` sau sort `published` desc | 5 | `row_count` 24→19 | Hit_rate 1.0→0.8 (2/10 câu) | Restore từ raw |
| Blank summary 3 | `df.iloc[0:3, summary_idx] = ""` | 3 | `summary` min_length FAIL | Text_for_embedding mất phần Summary | Restore từ raw |
| Inject noise 3 | `@@@###$$$` chèn vào summary | 3 | Embedding bị lệch | F1 giảm do text rác | Restore từ raw |
| Truncate title ≤5 | `title[:5]` trên 3 dòng | 3 | Quality không bắt (title không check) | Text relevance giảm | Restore từ raw |
| Stale date 5 | Lùi `published` -365 ngày, recompute `age_days` | 5 | `age_days>180` → stale_ratio tăng | Freshness SLA chưa vượt (5/21=23.8%) | Restore từ raw |
| Duplicate 2 | Nhân bản 2 dòng từ `tail()` | 2 (duplicate) | `paper_id` unique FAIL | Index có vector trùng | Restore từ raw |

**Total corruption effect:** 5+3+3+3+5+2 = 21 rows (5 dropped, 2 duplicated ≈ 24 input → 21 output)

**Corruption log:** `data/results/corruption_log.json`

- Status: ✅ Có
- Nhận xét: Log ghi đầy đủ 6 loại, affected_rows chính xác, NOISE_TOKEN="@@@###$$$", recompute `age_days` và `text_for_embedding` cho stale_date

**Cách repair đảm bảo dữ liệu phục hồi từ nguồn đáng tin cậy:**

`_repair_from_raw` đọc lại `data/raw/crossref_records.json` (raw snapshot đã bảo toàn) → chạy lại `build_clean_dataframe(load_raw_records(...), now_utc())` (hàm thuần túy, idempotent) → ghi đè cả `clean_*` và `repaired_*`. Không cố gắng "sửa ngược" từng lỗi mà chỉ chạy lại quy trình làm sạch từ dữ liệu gốc — đảm bảo kết quả tất định, có thể tái hiện.

---

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   |   1.0000 |    0.8000 |   1.0000 |                  -0.2000 |           +0.2000 | Giảm 20% (2/10 câu), phục hồi 100% |
| `mean_token_f1`        |   0.8000 |    0.6000 |   0.8000 |                  -0.2000 |           +0.2000 | Giảm 25%, phục hồi hoàn toàn |
| `judge_accuracy`       |   0.7000 |    0.5000 |   0.7000 |                  -0.2000 |           +0.2000 | Giảm 28.6% (2 câu), phục hồi |
| `mean_judge_score`     |   4.0000 |    3.5000 |   4.0000 |                  -0.5000 |           +0.5000 | Giảm 0.5 điểm, phục hồi |
| Quality checks pass/fail |    6/6 ✅ |      4/6 ❌ |    6/6 ✅ |          2 FAIL (unique+length) |           2 PASS | Phục hồi qua quality gate |
| Freshness status         |   ✅ Fresh |    ✅ Fresh |   ✅ Fresh |              5/21 stale (23.8%) |         0/24 stale | SLA chưa vượt (< 25% threshold) |

**Kết luận hai chuỗi nguyên nhân–bằng chứng:**

1. **[Data corruption: drop 5 + blank 3 + noise 3 + truncate 3 + stale 5 + duplicate 2]** → **[Quality Gate 6/6 PASS → 4/6 FAIL (paper_id not unique, summary too short); row count 24 → 21; stale 0/24 → 5/21]** → **[retrieval_hit_rate 1.0 → 0.8 (2 câu mất hit); mean_token_f1 0.8 → 0.6; judge_accuracy 0.7 → 0.5]**. Tín hiệu quality gate đi trước (mất unique key, độ dài summary) và dự báo được suy giảm ở tầng RAG agent.

2. **[Repair: load_raw_records + build_clean_dataframe idempotent]** → **[Quality Gate 4/6 FAIL → 6/6 PASS; row count 21 → 24; stale 5/21 → 0/24]** → **[retrieval_hit_rate 0.8 → 1.0; mean_token_f1 0.6 → 0.8; judge_accuracy 0.5 → 0.7]**. Phục hồi hoàn toàn trên cả ba lớp bằng chứng: quality gate green, metrics trở về baseline, tính idempotent được chứng minh.

**Corruption nào ảnh hưởng rõ nhất và vì sao?**

Nhóm **drop 5 bản ghi mới nhất** ảnh hưởng rõ nhất tới `retrieval_hit_rate`: 5 paper_id bị xóa khỏi index nên 2/10 câu hỏi có `ground_truth_doc_ids` trỏ vào chúng mất hit ngay. Kèm **duplicate 2** làm `paper_id` mất duy nhất (quality gate FAIL), vector trùng chiếm chỗ top-4 trong cosine search. Ba kịch bản **blank summary / inject noise `@@@###$$$` / truncate title** ảnh hưởng trực tiếp `mean_token_f1` vì `text_for_embedding` bị rỗng/nhiễu/cụt, làm sai embedding cosine. Ngược lại, **stale_date** (lùi 5 dòng 365 ngày) ảnh hưởng `age_days` nhưng trong lần chạy này chưa vượt ngưỡng freshness 25% (5/21=23.8%) — đúng như thiết kế hai tầng độc lập: stale kiểm soát SLA thời gian, drop/duplicate kiểm soát truy hồi.

**Kết quả nào khác với kỳ vọng ban đầu?**

Kỳ vọng ban đầu: corrupted `is_fresh` phải thành `False` khi stale > 25%. Thực tế: `is_fresh` vẫn `True` (5/21 = 23.8% < 25%). Đã kiểm tra `data/quality/corrupted_freshness_report.json` (stale_rows=5, total=21, stale_ratio=0.238) và `corruption_log.json` (stale_date count=5). Kết luận trung thực: ngưỡng 25% khá cao cho 21 rows — cần ≥6 stale mới vượt. Nếu muốn demo SLA FAIL trong cấu hình hiện tại cần tăng `count` stale hoặc giảm ngưỡng, nhưng không sửa số liệu để ép kết quả: **dữ liệu thực tế chứng minh là có 23.8% stale, đúng như vậy.**

---

## 11. Vấn đề tích hợp quan trọng

**Triệu chứng:** Import `build_embeddings` / `MiniLMEmbeddings` từ `retrieval.embeddings` không tìm thấy; curl `/v1/models` trả 401 unauthorized; Python script print tiếng Việt bị `cp1252` encode error trên Windows PowerShell.

**Nguyên nhân:** 
- `retrieval/embeddings.py` đã đổi sang `CustomOpenAIEmbeddings` nhưng `retrieval/__init__.py`, `index.py`, `evaluation/metrics.py` vẫn import cũ.
- Custom API yêu cầu `Authorization: Bearer <CUSTOM_LLM_API_KEY>`, curl thiếu header.
- Windows PowerShell dùng `cp1252` encoding mặc định, không support tiếng Việt.

**Cách xử lý:**
- Thêm `def build_embeddings(settings): return CustomOpenAIEmbeddings(settings)` và `MiniLMEmbeddings = CustomOpenAIEmbeddings` trong `embeddings.py` + re-export từ `__init__.py`.
- Thêm header `Authorization: Bearer $CUSTOM_LLM_API_KEY` vào tất cả curl commands và `requests.post` trong `CustomOpenAIEmbeddings`.
- Chạy pipeline với `PYTHONIOENCODING=utf-8` và đổi print thành ASCII-safe (`[OK] Ket noi ...` thay vì emoji/tiếng Việt trực tiếp).

**Cách xác minh:** `PYTHONPATH=./src PYTHONIOENCODING=utf-8 python script/run_phase1.py` chạy thành công, in "[OK] Ket noi embedding thanh cong (vector size: 1024)" và "[OK] Ket noi LLM thanh cong".

---

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| Fallback MiniLM đã xóa — tuỳ thuộc LM Studio | Nếu custom API offline, pipeline fail fast | Thêm graceful retry với exponential backoff; hoặc cache embeddings trước demo |
| `mean_token_f1` 0.8 ở baseline có thể do thiết kế: `_extract_answer` trích thẳng từ metadata (tác giả/xuất bản/lĩnh vực) mà test set cũng dùng trường đó → so một trường với chính nó | Không phản ánh đúng retrieval challenge | Tách ground truth khỏi metadata: sinh ground truth từ multi-hop query (kết hợp 2–3 tài liệu), `mean_token_f1` sẽ giảm xuống <1.0 realistic hơn |
| Chưa có RAGAS metrics (slower evaluation) | RAGAS disabled nếu `RUN_RAGAS != 1` để tiết kiệm thời gian demo 3–5 phút | Chạy RAGAS offline trước demo hoặc cache kết quả; hoặc implement RAGAS async background |
| ChromaDB manifest ghi `persist_path` tương đối nhưng chứa UUIDs dài — không dễ debug | Không ảnh hưởng tính năng nhưng tăng size manifest | Simplify manifest ghi chỉ backend + embedding_model + collection_name, skip UUID |
| GX 1.x 6 expectations thiếu data drift detection | Silent drift (schema thay đổi) không bắt được | Thêm expectation `ExpectColumnToExist` + `ExpectColumnValuesToBeInSet` để track domain changes |

---

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm, MSSV, repository chính xác (911Group, K4-L3A-Day10-911Group).
- [x] Phân công 3 thành viên khớp với module, artifact và kết quả thực tế (Minh orchestration, Hiếu ingestion/cleaning/quality, Cường corruption/repair).
- [x] Lệnh tái hiện đã được chạy lại trên code nộp: `PYTHONPATH=./src PYTHONIOENCODING=utf-8 python script/run_phase1.py` ✅ PASS (24 rows, 10 TV questions, hit 1.0, quality 6/6).
- [x] Baseline, corrupted, repaired dùng cùng evaluation set (`data/eval/test_set.json` 10 questions).
- [x] Bảng metrics khớp với files: `baseline_metrics.json` (hit 1.0, F1 0.8, judge 0.7), `corrupted_metrics.json` (hit 0.8, F1 0.6, judge 0.5), `repaired_metrics.json` (hit 1.0, F1 0.8, judge 0.7).
- [x] Quality/freshness conclusions khớp với `data/quality/*`: baseline 6/6 PASS + is_fresh=True, corrupted 4/6 FAIL + is_fresh=True (5/21=23.8%), repaired 6/6 PASS + is_fresh=True.
- [x] Các đường dẫn báo cáo và artifact truy cập được: `data/raw/*`, `data/clean/*`, `data/embeddings/*`, `data/eval/test_set.json`, `data/quality/*`, `data/results/*`, `data/reports/*.md`.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng: `report/2A202602496_NguyenTrongMinh.md`, `report/2A202602488_DuongMinhHieu.md`, `report/2A202602604_LeManhCuong`.
- [x] Không có `.env` (chỉ `.env.example`), API key, token hoặc secret trong source, report, log hay ảnh.
- [x] `.env.example` dùng `sk-lm-test-key` (placeholder, không key thật).
- [x] Báo cáo nhóm không là bản sao nguyên văn của báo cáo cá nhân mà là tổng hợp, phân tích nguyên nhân–hậu quả, kết luận chung.
