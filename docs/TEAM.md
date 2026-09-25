# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `911Group`
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3-DAY10-911Group-DataPipeline`

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Nguyễn Trọng Minh | 2A202602496 | | Trưởng nhóm / Pipeline Integrator (`core/config.py`, `retrieval/embeddings.py`, `retrieval/llm.py`, `pipelines/phase1.py`, `pipelines/corruption_flow.py`, custom API wiring) | `report/2A202602496_NguyenTrongMinh.md` |
| 2 | Dương Minh Hiếu | 2A202602488 | | Data Ingestion & Cleaning Owner (`crossref.py`, `cleaning.py`, raw data, freshness SLA) | `report/2A202602488_DuongMinhHieu.md` |
| 3 | Lê Mạnh Cường | 2A202602604 | | RAG, Observability & Evaluation (`ingestion/corruption.py`, `quality.py` GX 1.x, `testset.py`, `reporting.py`, 6-way corruption, repair idempotency) | `report/2A202602604_LeManhCuong` |

*(Nhóm 3 thành viên theo `report/README.md` nhóm 3: Minh tích hợp + custom API, Hiếu ingestion/cleaning, Cường corruption/quality/reporting)*.

---

## # Cá nhân

### ## NguyễnTrọngMinh-2A202602496
- **Vai trò:** Trưởng nhóm & Pipeline Integrator (custom API, orchestration).
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập cấu hình hệ thống `core/config.py` (`LLM_PROVIDER=custom`, `EMBEDDING_MODEL=text-embedding-bge-m3`, `CUSTOM_LLM_BASE_URL=http://127.0.0.1:1234/v1`).
  - Tích hợp `retrieval/embeddings.py` (CustomOpenAIEmbeddings qua POST /v1/embeddings, batch 32, 1024-dim bge-m3) và `retrieval/llm.py` (ternary-bonsai-8b).
  - Quản lý `retrieval/index.py` (ChromaDB 3 collections, cosine, manifest custom-openai-compatible).
  - Orchestrate `pipelines/phase1.py` (8 bước baseline) và `pipelines/corruption_flow.py` (corruption+repair+comparison).
- **Điều học được / Đóng góp chính:**
  - Thiết kế Idempotent Pipeline, wiring custom API qua environment, quản lý trạng thái 3-state luồng dữ liệu đa tầng.

### ## DươngMinhHiếu-2A202602488
- **Vai trò:** Data Ingestion & Cleaning Owner (raw preservation, quality gate).
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng module thu thập Crossref API dual-mode với fallback offline trong `src/ingestion/crossref.py`.
  - Chuẩn hóa schema, tính toán `age_days` và `text_for_embedding` 5-field trong `src/ingestion/cleaning.py`.
  - Thiết lập GX 1.x ephemeral context (6 expectations) + Freshness SLA (age_days>180, ratio≤0.25) trong `src/observability/quality.py`.
- **Điều học được / Đóng góp chính:**
  - Data lineage & raw snapshot preservation, cơ chế chốt kiểm dịch in-memory GX 1.x, phát hiện Silent Failure.

### ## LêMạnhCường-2A202602604
- **Vai trò:** RAG, Observability & Evaluation (corruption, quality, repair validation).
- **Công việc chi tiết đã hoàn thành:**
  - Triển khai 6 kịch bản corruption tính rời nhau (drop 5 / blank 3 / noise 3 / truncate 3 / stale 6 / duplicate 5) trong `src/ingestion/corruption.py`.
  - Ghi log chi tiết + xây dựng `testset.py` (10 câu hỏi 4 loại Vietnamese round-robin) + reporting 3-state.
  - Xác minh repair idempotent (load raw → build_clean → overwrite clean/repaired) via `corruption_flow.py`.
- **Điều học được / Đóng góp chính:**
  - Disjointness của phép biến đổi, Silent Failure thầm lặng, tầng kiểm tra độc lập (row_count vs khóa duy nhất).
