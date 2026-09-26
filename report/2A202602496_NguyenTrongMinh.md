# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                          |
| ----------------- | ------------------------------------------------- |
| Họ và tên         | Nguyễn Trọng Minh                                 |
| MSSV              | 2A202602496                                       |
| Khóa/Lớp          | K4                                                |
| Tên nhóm          | 911Group                                          |
| Vai trò chính     | Trưởng nhóm / Pipeline Integrator & Orchestration |
| Repository        | https://github.com/EntityEbisu/K4-L3A-Day10-911Group |
| Ngày hoàn thành   | 2026-09-25                                        |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **Cấu hình & Orchestration** | `src/core/config.py` — `load_settings`, `Paths`, `Settings`, `require_llm_credentials`; `src/core/utils.py` | `.env` (`LLM_PROVIDER=custom`, `CUSTOM_LLM_BASE_URL`, `EMBEDDING_MODEL=text-embedding-bge-m3`) | `Settings` thống nhất cho toàn pipeline, 20+ `Paths` artifact | Hoàn thành |
| **Baseline Orchestration** | `src/pipelines/phase1.py` — `main` (8 bước) | `Settings`, raw snapshot | `data/clean/papers_clean.*`, `data/eval/test_set.json`, `data/embeddings/papers_embeddings.json`, `data/quality/*`, `data/results/baseline_*`, `data/reports/phase1_report.md` | Hoàn thành |
| **Corruption → Repair Flow** | `src/pipelines/corruption_flow.py` — `main` | `papers_clean.json` + `baseline_metrics.json` + raw snapshot | `papers_clean_corrupted/repaired.*`, `corrupted/repaired_metrics.json`, `corruption_log.json`, `data/reports/corruption_report.md` (3 cột) | Hoàn thành |
| **Tích hợp Embedding/LLM custom API** | `src/retrieval/embeddings.py` — `CustomOpenAIEmbeddings`; `src/retrieval/llm.py` — `build_llm`; `src/retrieval/index.py` — `LocalEmbeddingIndex` | `CUSTOM_LLM_BASE_URL=http://127.0.0.1:1234/v1`, `EMBEDDING_MODEL=text-embedding-bge-m3`, `LLM_MODEL=ternary-bonsai-8b` | ChromaDB 3 collections (`papers-baseline/corrupted/repaired`, cosine), manifest `backend=custom-openai-compatible` | Hoàn thành |
| **Điều phối nhóm & kiểm soát chất lượng nộp bài** | `docs/TEAM.md`, `report/*`, `.env.example`, git history | Phân công 3 thành viên, artifacts thực tế | TEAM.md, báo cáo cá nhân 3 thành viên, `.env.example` không chứa secret, commit history sạch | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| :--- | :--- | :--- |
| Chẩn đoán custom API trước khi sửa code (Phase 0) | Toàn pipeline | Xác minh `GET /v1/models` + `POST /v1/embeddings` (vector 1024-dim bge-m3) + `POST /v1/chat/completions` (ternary-bonsai-8b) đều qua Bearer token; chặn việc revert về MiniLM |
| Sửa lệch import `build_embeddings` / `MiniLMEmbeddings` | `retrieval/__init__.py`, `retrieval/index.py`, `evaluation/metrics.py` | Thay bằng `CustomOpenAIEmbeddings` + alias tương thích, pipeline chạy lại không lỗi `ImportError` |
| Chuẩn hóa `.env.example` và xử lý encoding Windows | Toàn nhóm | `.env.example` dùng `sk-lm-test-key` (không lộ key thật), `PYTHONIOENCODING=utf-8` tránh lỗi `cp1252` trên PowerShell |
| Rà soát artifact trước nộp | Observability & Ingestion | Đối chiếu `baseline/corrupted/repaired_metrics.json` với `corruption_report.md`, phát hiện corrupted `is_fresh=True` vẫn trong ngưỡng (5/21 = 23.8%) — ghi nhận trung thực thay vì ép kết luận sai |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| :--- | :--- | :--- | :--- |
| Thiết kế `Settings`/`Paths` và chuẩn hóa custom provider | `src/core/config.py`, `.env.example` | `LLM_PROVIDER=custom`, `EMBEDDING_MODEL=text-embedding-bge-m3`, `CUSTOM_LLM_BASE_URL` load đúng từ `.env` (workspace + root), `require_llm_credentials` chặn thiếu `CUSTOM_LLM_BASE_URL` | `python -c "from core.config import load_settings; s=load_settings(); print(s.llm_provider, s.embedding_model, s.custom_llm_base_url)"` |
| Chẩn đoán kết nối LLM + Embedding trước Phase 1 | `src/retrieval/embeddings.py`, `src/retrieval/llm.py` | `CustomOpenAIEmbeddings.embed_query` trả vector 1024-dim; `build_llm(...).invoke("Xin chào")` trả lời tiếng Việt | `curl -H "Authorization: Bearer $CUSTOM_LLM_API_KEY" $CUSTOM_LLM_BASE_URL/models` + probe python trực tiếp |
| Orchestrate baseline 8 bước | `src/pipelines/phase1.py`, `script/run_phase1.py` | 24 raw → 24 clean, 10 câu hỏi TV, 3 collections ChromaDB, quality 6/6, freshness 0/24, hit 1.0, F1 0.8, phase1_report.md | `python script/run_phase1.py` |
| Orchestrate corruption → repair → so sánh 3 trạng thái | `src/pipelines/corruption_flow.py`, `script/run_corruption_flow.py` | corrupted 21 rows, 6 kịch bản (5/3/3/3/5/2), quality 4/6, hit 0.8 F1 0.6; repaired 24 rows, quality 6/6, hit 1.0 F1 0.8; `corruption_report.md` 3 cột | `python script/run_corruption_flow.py` + `cat data/results/corruption_log.json` |
| Tích hợp vector store idempotent | `src/retrieval/index.py` | `LocalEmbeddingIndex.build` xóa/recreate collection, `configuration={"hnsw":{"space":"cosine"}}`, manifest ghi `persist_path` tương đối + `backend=custom-openai-compatible` | `cat data/embeddings/papers_embeddings*.json` |

**Một output cụ thể mà phần việc của tôi tạo ra và trực tiếp xác minh:**
Chuỗi orchestration khép kín `phase1.py` → `corruption_flow.py` sinh ra đầy đủ 21 artifacts có thể liệt kê bằng `find data -type f | sort`: `data/raw/*` (2), `data/clean/*` (6), `data/embeddings/*` (3), `data/eval/test_set.json` (10 câu hỏi TV), `data/quality/*` (6), `data/results/*` (7), `data/reports/*` (2). Trong đó `data/reports/corruption_report.md` là bằng chứng cuối cùng tôi chịu trách nhiệm: bảng 3 cột cho thấy `retrieval_hit_rate` 1.0 → 0.8 → 1.0 và `mean_token_f1` 0.8 → 0.6 → 0.8, chứng minh corruption gây suy giảm có đo được và repair idempotent khôi phục hoàn toàn.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

1. Pipeline 7 tầng (ingest → clean → quality gate → index → benchmark → corruption → repair) cần một điểm cấu hình duy nhất và một trình tự chạy có thể tái lập, không phụ thuộc thứ tự thủ công.
2. Lab yêu cầu dùng custom OpenAI-compatible API (`http://127.0.0.1:1234/v1`) cho cả LLM (`ternary-bonsai-8b`) và embedding (`text-embedding-bge-m3`) — không được fallback về `sentence-transformers/all-MiniLM-L6-v2`. Trước khi sửa bất kỳ file nào phải chứng minh cả hai endpoint đều gọi được (Phase 0 read-only).
3. Orchestration phải đảm bảo: raw snapshot được bảo toàn, clean là hàm thuần túy của (raw, run_date) để repair idempotent, test set được giữ nguyên qua 3 trạng thái, và mọi manifest/report ghi đường dẫn tương đối (không lộ đường dẫn Windows tuyệt đối).

### Cách triển khai

1. **Config (`core/config.py`):** `load_settings()` đọc `.env` từ `workspace/.env` rồi `root/.env` (override=False), gom 20+ đường dẫn artifact vào `Paths`, tính `source_from_date = today - 180 ngày` cho filter Crossref. `embedding_model` mặc định `text-embedding-bge-m3` (đọc từ `EMBEDDING_MODEL`), không phải MiniLM. `normalized_provider` chuẩn hóa `custom`/`customllm`, `require_llm_credentials` bắt buộc `CUSTOM_LLM_BASE_URL` khi `LLM_PROVIDER=custom`.

2. **Custom Embeddings (`retrieval/embeddings.py`):** `CustomOpenAIEmbeddings(Embeddings)` dùng `requests.post(f"{base}/embeddings", json={"model": model, "input": batch}, headers={"Authorization": f"Bearer {api_key}"})`, batch 32, sắp xếp lại theo `index` trả về, timeout 120s. `embed_query` gọi `embed_documents([text])[0]`. Alias `MiniLMEmbeddings = CustomOpenAIEmbeddings` và `build_embeddings = CustomOpenAIEmbeddings` giữ tương thích import cũ.

3. **LLM (`retrieval/llm.py`):** `build_llm` nhánh `provider==custom` trả `ChatOpenAI(model=settings.model_name, api_key=settings.custom_llm_api_key or "unused", base_url=settings.custom_llm_base_url)`, các provider khác giữ nguyên.

4. **Vector Index (`retrieval/index.py`):** `LocalEmbeddingIndex.build(df, settings, manifest_path)` tạo `PersistentClient(path=chroma_dir)`, `delete_collection` nếu tồn tại rồi `create_collection(..., configuration={"hnsw":{"space":"cosine"}})`, embed `text_for_embedding`, `add(ids, embeddings, documents, metadatas)`. Manifest ghi `backend=custom-openai-compatible`, `embedding_model`, `persist_path` tương đối. `load` resolve lại đường dẫn tương đối.

5. **Phase 1 (`pipelines/phase1.py`):** 8 bước tuần tự — (1) verify embedding (vector non-empty) + LLM invoke, (2) load raw (dual-mode: nếu `refresh_source==False` và snapshot tồn tại thì dùng snapshot, else fetch với retry 429/503), (3) `build_clean_dataframe`, (4) lưu clean CSV/JSON, (5) build test set (chỉ refresh nếu `REFRESH_TEST_SET` hoặc câu hỏi đầu không phải TV), (6) build index, (7) `run_data_quality_checks` + `build_freshness_report`, (8) `evaluate_pipeline` + `generate_phase1_report`. Mọi `print` dùng ASCII-safe (`[OK]`) để tránh lỗi `cp1252`.

6. **Corruption Flow (`pipelines/corruption_flow.py`):** Kiểm tra `clean_json` + `baseline_metrics` tồn tại, đọc `corruption_log` counts, chạy `corrupt_clean_dataframe` (6 kịch bản), quality/freshness + index + evaluate cho corrupted, rồi repair: `build_clean_dataframe(load_raw_records(raw_records_json), now_utc())` ghi đè cả `repaired_*` lẫn `clean.*` (idempotent), rebuild `papers-repaired`, quality/freshness + evaluate cho repaired, cuối cùng `generate_corruption_report` + in bảng 3 trạng thái ra console.

### Input, output và contract

| Thành phần | Mô tả |
| :--- | :--- |
| **Input** | `.env` (custom base URL/key/model), `data/raw/crossref_records.json` (24 PaperRecord), `Settings` |
| **Output** | `Settings`/`Paths`; 21 artifacts data/*; 2 báo cáo markdown; ChromaDB 3 collections |
| **Module phụ thuộc** | `core.config`, `core.utils` (`write_json` ensure_ascii=False), `ingestion/*`, `observability/*`, `retrieval/*`, `evaluation/*` |
| **Module sử dụng output** | Mọi module pipeline đọc `Settings.paths`; `evaluation/metrics.py` đọc index + test set; `docs/TEAM.md` và `report/*` đối chiếu artifacts |
| **Điều kiện lỗi cần xử lý** | Custom API unreachable / 401 / 400 (fail fast, không fallback MiniLM); snapshot thiếu khi offline; `NaN` trong GX report (chuyển `None`); `cp1252` encoding trên Windows |

### Cách xác minh

```bash
# 0. Chẩn đoán custom API (Phase 0, read-only)
curl -s -H "Authorization: Bearer $CUSTOM_LLM_API_KEY" http://127.0.0.1:1234/v1/models
PYTHONPATH=./src python -c "from core.config import load_settings; from retrieval.embeddings import CustomOpenAIEmbeddings; s=load_settings(); print(len(CustomOpenAIEmbeddings(s).embed_query('test')))"
PYTHONPATH=./src python -c "from core.config import load_settings; from retrieval.llm import build_llm; s=load_settings(); print(build_llm(s).invoke('Xin chào').content[:120])"

# 1. Baseline
PYTHONPATH=./src PYTHONIOENCODING=utf-8 python script/run_phase1.py

# 2. Corruption → Repair → So sánh 3 trạng thái
PYTHONPATH=./src PYTHONIOENCODING=utf-8 python script/run_corruption_flow.py

# 3. Đối chiếu metrics thực tế
cat data/results/baseline_metrics.json
cat data/results/corrupted_metrics.json
cat data/results/repaired_metrics.json
cat data/quality/baseline_quality_report.json
cat data/quality/corrupted_quality_report.json
cat data/quality/freshness_report.json
```

- **Kết quả mong đợi:** embed 1024-dim, LLM tiếng Việt, baseline 24 rows quality 6/6 hit 1.0, corrupted 21 rows quality 4/6 hit 0.8, repaired 24 rows quality 6/6 hit 1.0.
- **Kết quả thực tế:** Đúng như mong đợi (chi tiết §8). Corrupted `is_fresh=True` (5/21 = 23.8% < 25% ngưỡng) — vẫn trong SLA, ghi nhận trung thực.
- **Artifact/log:** `data/embeddings/*.json` (`backend=custom-openai-compatible`), `data/reports/*.md`, `data/results/*.json`, `data/quality/*.json`. Không chứa secret.

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lab yêu cầu embedding qua custom API (`POST /v1/embeddings`), nhưng codebase cũ rải rác `from retrieval.embeddings import build_embeddings` / `MiniLMEmbeddings` và `langchain_openai.OpenAIEmbeddings`. Cần quyết định giữ hay xóa fallback MiniLM.
- **Các phương án đã cân nhắc:**
  1. *Giữ dual-path:* `build_embeddings` thử custom trước, fallback MiniLM nếu custom lỗi — pipeline không fail fast, dễ che lỗi cấu hình.
  2. *Xóa MiniLM, chỉ custom:* `CustomOpenAIEmbeddings` gọi raw `requests` tới `/v1/embeddings`, mọi import cũ được alias về class này; nếu custom unreachable thì fail fast ngay ở Phase 1.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Đúng yêu cầu đề bài (`.env` ghi rõ `EMBEDDING_MODEL=text-embedding-bge-m3` qua custom API), tránh vector 384-dim MiniLM lẫn với 1024-dim bge-m3 gây sai cosine, và tuân thủ nguyên tắc observability: lỗi infra phải lộ ngay ở quality gate, không được silent fallback. Trade-off là pipeline phụ thuộc LM Studio phải bật — chấp nhận được vì dev_plan §9 ghi "evaluation/indexing requires custom service reachable".
- **Bằng chứng quyết định phù hợp:** Sau thay đổi, `data/embeddings/*.json` đều ghi `backend=custom-openai-compatible` + `embedding_model=text-embedding-bge-m3` (không còn `sentence-transformers/...`), probe `embed_query` trả 1024-dim, và `LocalEmbeddingIndex.build` với `space=cosine` cho hit rate 1.0 ở baseline.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```text
  ImportError: cannot import name 'build_embeddings' from 'retrieval.embeddings'
  ModuleNotFoundError: No module named 'pipelines'  (khi chạy python -m pipelines.phase1)
  UnicodeEncodeError: 'charmap' codec can't encode character 'ắ' / '\U0001f680'
  ```
  và `curl http://127.0.0.1:1234/v1/models` trả `{"error":"An LM Studio API token is required... invalid_api_key"}`

- **Lệnh hoặc bước tái hiện:**
  ```bash
  PYTHONPATH=./src python -c "from retrieval.index import LocalEmbeddingIndex"  # ImportError
  python -m pipelines.phase1                                                     # ModuleNotFoundError
  python script/run_phase1.py                                                    # UnicodeEncodeError trên PowerShell
  curl -s http://127.0.0.1:1234/v1/models                                       # 401 invalid_api_key
  ```

- **Nguyên nhân gốc:**
  1. `retrieval/embeddings.py` đã đổi sang `CustomOpenAIEmbeddings` nhưng `retrieval/__init__.py`, `retrieval/index.py`, `evaluation/metrics.py` vẫn import `build_embeddings`/`MiniLMEmbeddings` cũ.
  2. `pipelines` nằm dưới `src/`, cần `PYTHONPATH=./src` hoặc entrypoint `script/run_*.py`.
  3. `print` chứa emoji/tiếng Việt có dấu bị `cp1252` trên Windows PowerShell.
  4. Custom API yêu cầu `Authorization: Bearer <CUSTOM_LLM_API_KEY>`, curl thiếu header.

- **Cách xử lý:**
  1. Trong `retrieval/embeddings.py` thêm `def build_embeddings(settings): return CustomOpenAIEmbeddings(settings)` và `MiniLMEmbeddings = CustomOpenAIEmbeddings`; sửa `retrieval/__init__.py` re-export cả hai; sửa `retrieval/index.py` và `evaluation/metrics.py` import `CustomOpenAIEmbeddings`.
  2. Dùng `script/run_phase1.py` + `PYTHONPATH=./src` cho mọi lệnh.
  3. Đổi `print("✓ ...")` / emoji thành `[OK] ...` ASCII-safe, chạy với `PYTHONIOENCODING=utf-8`.
  4. Thêm header `Authorization: Bearer $CUSTOM_LLM_API_KEY` vào curl và `requests` trong `CustomOpenAIEmbeddings`.

- **Cách xác minh sau khi sửa:**
  ```bash
  PYTHONPATH=./src python -c "from retrieval.embeddings import CustomOpenAIEmbeddings, build_embeddings, MiniLMEmbeddings; print('imports ok')"
  curl -s -H "Authorization: Bearer $CUSTOM_LLM_API_KEY" http://127.0.0.1:1234/v1/models | python -m json.tool | head -n 20
  PYTHONPATH=./src PYTHONIOENCODING=utf-8 python script/run_phase1.py   # in "[OK] Ket noi embedding thanh cong (vector size: 1024)"
  ```

- **Điều học được:** Khi đổi provider, phải grep toàn repo các import cũ (`build_embeddings`, `MiniLM`) trước khi commit; và mọi probe custom API phải kèm Bearer token ngay từ đầu. Trên Windows, luôn đặt `PYTHONIOENCODING=utf-8` cho pipeline in tiếng Việt.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   `fetch_source_records` (dual-mode: nếu `refresh_source=False` và snapshot tồn tại thì đọc `data/raw/crossref_records.json`, else gọi `https://api.crossref.org/works` với retry 429/503 và persist cả `crossref_response.json` + `crossref_records.json`) → `parse_crossref_payload` strip JATS (`<jats:...>`) và chuẩn hóa fallback chain `issued → published → published-print → published-online → created` về `YYYY-MM-DD` → `build_clean_dataframe` (strip JATS, normalize whitespace, parse `published` UTC, tính `age_days=(run_date - published).days`, dựng `text_for_embedding` 5 dòng Title/Authors/Published/Categories/Summary, dedup `paper_id`, sort `published` desc) → `LocalEmbeddingIndex.build` embed `text_for_embedding` qua `POST /v1/embeddings` (bge-m3 1024-dim) → ChromaDB `PersistentClient` collection `papers-baseline` (cosine).

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   `build_test_set` sort `paper_id`, round-robin 4 loại câu hỏi TV (`tóm tắt`/`tác giả`/`xuất bản`/`lĩnh vực`), sinh 10 bản ghi `eval_001..010` với `ground_truth_doc_ids=[paper_id]` và `ground_truth` (câu đầu của summary cho loại tóm tắt, `authors_joined`/`published`/`categories_joined` cho các loại còn lại). Khi `evaluate_pipeline` chạy, với mỗi câu hỏi: `retrieval_hit_rate` = ground truth doc có trong top-k `LocalEmbeddingIndex.search` không; `mean_token_f1` = F1 token giữa `qa.py::_extract_answer` (trích theo từ khóa TV `tác giả`/`xuất bản`/`lĩnh vực`/`tóm tắt`) và `ground_truth`; `judge_accuracy`/`mean_judge_score` = LLM judge (`build_llm` custom) chấm structured `JudgeVerdict`.

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   Quality checks (GX 1.x ephemeral: `ExpectTableRowCountToBeBetween 5-5000`, `ExpectColumnValuesToNotBeNull` cho `paper_id`/`title`/`text_for_embedding`, `ExpectColumnValuesToBeUnique` cho `paper_id`, `ExpectColumnValueLengthsToBeBetween summary ≥30`) kiểm tra tính toàn vẹn cấu trúc/ngữ nghĩa tại thời điểm chạy. Freshness monitoring kiểm tra chiều thời gian: `stale = age_days > 180`, `stale_ratio = stale/total`, `is_fresh = stale_ratio ≤ 0.25`. Dữ liệu có thể sạch về cấu trúc nhưng cũ, hoặc tươi nhưng rỗng — vì vậy gate cuối là `success AND is_fresh`, hai tín hiệu độc lập.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Để phép so sánh 3 trạng thái là controlled experiment: chỉ biến `data` đổi, biến `test set` giữ nguyên. Nếu mỗi trạng thái sinh test set mới thì chênh lệch metric có thể do câu hỏi khác nhau, không quy được về chất lượng dữ liệu. `phase1.py` chỉ refresh khi `REFRESH_TEST_SET` hoặc câu hỏi đầu không phải TV; `corruption_flow.py` tái sử dụng `data/eval/test_set.json` nguyên vẹn.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   Ba lớp: (a) artifact — `papers_clean_repaired.csv/.json` trùng khớp `papers_clean.csv/.json` khi sort theo `paper_id` (vì repair là `load_raw_records` → `build_clean_dataframe(now_utc())` idempotent, không sửa ngược từng lỗi); (b) observability — `repaired_quality_report.json` 6/6 và `repaired_freshness_report.json` `is_fresh=True` (0/24 stale); (c) metrics — `repaired_metrics.json` trở về `baseline_metrics.json` (`retrieval_hit_rate` 0.8→1.0, `mean_token_f1` 0.6→0.8, `judge_accuracy` 0.5→0.7). Chỉ khi cả ba lớp cùng đạt mới kết luận repair thành công.

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| :--- | :---: | :---: | :---: | :--- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | Giảm 20% (2/10 câu mất hit) do mất 5 bản ghi mới nhất + duplicate làm nhiễu top-k; repair khôi phục hoàn toàn. |
| `mean_token_f1` | 0.8000 | 0.6000 | 0.8000 | Giảm 25%; F1 nhạy với blank summary + noise `@@@###$$$` + title ≤5 ký tự. |
| `judge_accuracy` | 0.7000 | 0.5000 | 0.7000 | Giảm 28.6% (2 câu đổi verdict); thang nhị phân nên mỗi câu = 10%. |
| `mean_judge_score` | 4.0000 | 3.5000 | 4.0000 | Giảm 0.5 điểm trên thang 1–5. |
| Quality checks | 6/6 PASS | 4/6 FAIL | 6/6 PASS | Corrupted FAIL đúng 2 expectation: `paper_id` not unique (duplicate) và `summary` min_length (blank). |
| Freshness status | 0/24, `is_fresh=True` | 5/21, `is_fresh=True` (23.8% < 25%) | 0/24, `is_fresh=True` | Corrupted stale do lùi 5 dòng về 365 ngày trước nhưng chưa vượt ngưỡng 25% nên SLA chưa kích hoạt — đây là điểm cần ghi trung thực, không ép thành `False`. |

### Kết luận từ số liệu

1. **[Data corruption: drop 5 mới nhất + blank 3 + noise 3 + truncate 3 + stale 5 + duplicate 2]** → **[Quality 6/6 → 4/6 (mất unique + min_length); total rows 24 → 21 (drop 5 bù 2 dup); stale 0/24 → 5/21]** → **[retrieval_hit_rate 1.0→0.8; mean_token_f1 0.8→0.6; judge_accuracy 0.7→0.5]**. Tín hiệu quality gate đi trước và dự báo được suy giảm RAG.

2. **[Repair: load_raw_records + build_clean_dataframe (idempotent)]** → **[Quality 4/6→6/6; stale 5/21→0/24; rows 21→24]** → **[retrieval_hit_rate 0.8→1.0; mean_token_f1 0.6→0.8; judge_accuracy 0.5→0.7]**. Repair khôi phục hoàn toàn về baseline trên cả 3 lớp bằng chứng (artifact + quality + metrics).

**Corruption nào ảnh hưởng rõ nhất và vì sao?**

Nhóm **drop 5 bản ghi mới nhất** ảnh hưởng rõ nhất tới `retrieval_hit_rate`: 5 paper_id bị xóa khỏi index nên 2/10 câu hỏi có `ground_truth_doc_ids` trỏ vào chúng mất hit ngay. Kèm **duplicate 2** làm `paper_id` mất duy nhất, vector trùng chiếm chỗ top-k. Ba kịch bản **blank summary / inject noise `@@@###$$$` / truncate title ≤5** ảnh hưởng trực tiếp `mean_token_f1` vì `text_for_embedding` bị rỗng/nhiễu/cụt. Ngược lại, **stale_date** (lùi 5 dòng 365 ngày) trong lần chạy này *chưa* vượt ngưỡng freshness 25% (5/21=23.8%) nên không kích hoạt `is_fresh=False` — đúng như thiết kế hai tầng độc lập: stale ảnh hưởng SLA thời gian, không ảnh hưởng hit rate.

**Kết quả nào khác với kỳ vọng ban đầu?**

Kỳ vọng ban đầu: corrupted `is_fresh` phải thành `False`. Thực tế: `is_fresh` vẫn `True` (5/21 = 23.8% < 25%). Giả thuyết: ngưỡng 25% khá cao, cần ≥6 stale trên 24 mới vượt. Đã kiểm tra bằng `cat data/quality/corrupted_freshness_report.json` (stale_rows 5, total 21) và `corruption_log.json` (stale_date count 5). Kết luận trung thực: corruption stale_date có tác động nhưng chưa đủ vượt SLA trong cấu hình hiện tại — nếu muốn demo SLA FAIL cần tăng `count` stale hoặc giảm ngưỡng, nhưng không sửa số liệu để ép kết quả.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Orchestration là contract, không chỉ là thứ tự chạy.** Việc gom mọi `Paths` vào `Settings` và để `phase1.py`/`corruption_flow.py` chỉ đọc `Settings` giúp 3 trạng thái dùng cùng test set, cùng collection config (cosine), cùng manifest tương đối — mọi lệch lạc đều lộ ngay khi diff artifact.

2. **Data quality và freshness là hai trục trực giao.** Trong thí nghiệm này `row_count` vẫn PASS khi dữ liệu đã hỏng (21 rows vẫn trong [5,5000]), chỉ `unique` và `min_length` bắt được lỗi; ngược lại stale 5/21 vẫn PASS freshness. Một gate duy nhất không đủ — cần ít nhất 3 loại check (count, semantic, temporal).

3. **Chọn custom API thì phải fail fast.** Giữ fallback MiniLM sẽ che lỗi cấu hình (`CUSTOM_LLM_BASE_URL` sai, key hết hạn) bằng vector 384-dim im lặng — RAG vẫn chạy nhưng số liệu vô nghĩa. Fail fast ở Phase 1 (embed probe + LLM invoke) giúp demo 3–5 phút không bị silent failure.

### Nếu có thêm thời gian

Tách `qa.py::_extract_answer` khỏi việc so sánh trực tiếp metadata với ground truth (hiện làm `mean_token_f1` dễ đạt 1.0 giả tạo ở baseline) bằng cách thêm nhóm câu hỏi multi-hop tổng hợp 2–3 tài liệu và để ground truth là câu trả lời tổng hợp, không phải trích nguyên trường. Cách đo cải thiện: baseline `mean_token_f1` sẽ giảm xuống <1.0 (trung thực hơn) và chênh lệch corrupted→repaired sẽ phản ánh đúng năng lực RAG thay vì độ trùng metadata.

---

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Trọng Minh
**Ngày xác nhận:** 2026-09-25
