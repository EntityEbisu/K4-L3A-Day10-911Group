# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                                                  |
| ----------------- | ------------------------------------------------------------------------- |
| Họ và tên         | Dương Minh Hiếu                                                           |
| MSSV              | 2A202602488                                                               |
| Khóa/Lớp          | K4                                                                        |
| Tên nhóm          | 911Group                                                                  |
| Vai trò chính     | Data ingestion & cleaning owner                                           |
| Repository        | https://github.com/EntityEbisu/K4-L3A-Day10-911Group/tree/main            |
| Ngày hoàn thành   | 2026-09-25                                                                |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **Data Ingestion & Raw Preservation** | `src/ingestion/crossref.py`:<br>- `parse_crossref_payload`<br>- `fetch_source_records`<br>- `load_raw_records` | REST API payload Crossref hoặc snapshot JSON offline | `data/raw/crossref_response.json`<br>`data/raw/crossref_records.json`<br>`list[PaperRecord]` (24 records) | Hoàn thành |
| **Data Cleaning & Embedding Modeling** | `src/ingestion/cleaning.py`:<br>- `build_clean_dataframe`<br>- `_calculate_age_days` | `list[PaperRecord]`, `run_date` | `data/clean/papers_clean.csv`<br>`data/clean/papers_clean.json`<br>`pd.DataFrame` (24 rows sạch, kèm `text_for_embedding`, `age_days`) | Hoàn thành |
| **Data Quality Gate & Freshness SLA** | `src/observability/quality.py`:<br>- `run_data_quality_checks`<br>- `build_freshness_report` | `pd.DataFrame` clean, `Settings` | `data/quality/test_quality_report.json` (GX 1.x success=True)<br>`data/quality/freshness_report.json` (is_fresh=True) | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| :--- | :--- | :--- |
| Cấu hình môi trường & xử lý encoding Windows | Toàn bộ nhóm | Cấu hình `$env:PYTHONIOENCODING="utf-8"` giúp chạy lệnh CLI trên PowerShell không bị lỗi `cp1252` |
| Tích hợp chốt kiểm dịch Great Expectations 1.x | Nhóm Observability | Thiết lập Ephemeral Context chuẩn GX 1.x không phát sinh file rác, định nghĩa 4 expectations chuẩn |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| :--- | :--- | :--- | :--- |
| Thu thập & Cứu hộ Offline Crossref API | `src/ingestion/crossref.py` | Tải thành công 24 bài báo; tự động fallback snapshot khi HTTP 429 hoặc mất mạng | Chạy lệnh `fetch_source_records` kiểm tra số bài báo |
| Làm sạch, tính `age_days`, tạo `text_for_embedding` | `src/ingestion/cleaning.py`<br>`data/clean/papers_clean.csv`<br>`data/clean/papers_clean.json` | 24 dòng sạch, lọc bỏ rác JATS XML `<jats:p>`, khử trùng lặp theo `paper_id` | Chạy lệnh `build_clean_dataframe` |
| Thiết lập Quality Gate GX 1.x & Freshness SLA | `src/observability/quality.py`<br>`data/quality/freshness_report.json`<br>`data/quality/test_quality_report.json` | 100% Expectations Passed; Freshness SLA đạt chuẩn (`stale_ratio = 4.17% <= 25%`) | Chạy lệnh `run_data_quality_checks` |

**Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:**
- Dataset sạch [data/clean/papers_clean.json](file:///d:/K4-L3A-Day10-911Group/data/clean/papers_clean.json) gồm 24 bài báo khoa học chất lượng cao, mỗi bản ghi có trường `text_for_embedding` hoàn chỉnh 5 phần (Title, Authors, Published, Categories, Summary) và trường `age_days` chuẩn xác. Báo cáo chất lượng [data/quality/test_quality_report.json](file:///d:/K4-L3A-Day10-911Group/data/quality/test_quality_report.json) xác nhận `success: true` cho toàn bộ 6/6 lượt kiểm tra của Great Expectations 1.x.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
1. Dữ liệu thô từ Crossref API chứa nhiều định dạng không đồng nhất, các thẻ JATS XML rác (`<jats:p>...</jats:p>`), thực thể HTML (`&amp;`, `&lt;`) và khoảng trắng thừa.
2. Nguy cơ API quá tải (mã lỗi HTTP 429) hoặc mạng phòng lab chập chờn làm gián đoạn toàn bộ pipeline.
3. Cần bảo toàn data lineage từ raw đến clean, khử trùng lặp bài báo theo DOI, tính toán độ tươi dữ liệu (`age_days`) và đóng gói ngữ cảnh `text_for_embedding` chuẩn mực trước khi đưa vào Vector Store ChromaDB.
4. Cần chốt kiểm dịch dữ liệu tự động theo chuẩn Great Expectations 1.x ngăn chặn dữ liệu bẩn xâm nhập vào hệ thống RAG.

### Cách triển khai
1. **Module `crossref.py`**:
   - Sử dụng regex `re.sub(r"<[^>]+>", " ", text)` kết hợp `html.unescape()` để bóc tách abstract tinh gọn.
   - Chuẩn hóa tác giả (`given` + `family`), chuyên ngành (`subject`), ngày xuất bản theo chuẩn ISO 8601 (`YYYY-MM-DD`).
   - Xây dựng cơ chế **Dual-Mode Fallback**: Khi `refresh_source=True`, gọi REST API với timeout. Nếu dính mã 429, 503 hoặc mất mạng (`Exception`), hệ thống ghi log cảnh báo và tự động chuyển sang đọc snapshot [data/raw/crossref_response.json](file:///d:/K4-L3A-Day10-911Group/data/raw/crossref_response.json).
2. **Module `cleaning.py`**:
   - Tính toán `age_days = (run_date - published).days` an toàn về múi giờ giữa timezone-aware và timezone-naive.
   - Tạo trường `text_for_embedding` gồm 5 phần rõ ràng:
     ```text
     Title: <Tiêu đề>
     Authors: <Danh sách tác giả>
     Published: <Ngày xuất bản>
     Categories: <Chuyên ngành>
     Summary: <Tóm tắt nội dung>
     ```
   - Khử trùng lặp bản ghi qua `df.drop_duplicates(subset=["paper_id"], keep="first")`.
3. **Module `quality.py`**:
   - Khởi tạo Great Expectations ở chế độ `mode="ephemeral"` (chạy trên RAM, cực nhanh, không sinh file rác).
   - Thiết lập 4 kỳ vọng thiết yếu: `ExpectTableRowCountToBeBetween(5, 5000)`, `ExpectColumnValuesToNotBeNull`, `ExpectColumnValuesToBeUnique`, `ExpectColumnValueLengthsToBeBetween(summary >= 30)`.
   - Tính Freshness SLA: cảnh báo `is_fresh = False` nếu tỷ lệ bản ghi có `age_days > 180` vượt quá 25%.

### Input, output và contract

| Thành phần | Mô tả |
| :--- | :--- |
| **Input** | JSON payload từ Crossref REST API / Snapshot `crossref_response.json` |
| **Output** | `data/raw/crossref_records.json`, `data/clean/papers_clean.csv`, `data/clean/papers_clean.json`, `freshness_report.json` |
| **Module phụ thuộc** | `core.config.Settings` |
| **Module sử dụng output** | `src/retrieval/index.py` (ChromaDB indexing), `src/evaluation/testset.py`, `src/pipelines/phase1.py` |
| **Điều kiện lỗi cần xử lý** | Mất mạng, HTTP 429, ngày tháng thiếu `date-parts`, abstract rỗng, trùng DOI |

### Cách xác minh

```bash
# 1. Xác minh Ingestion
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"

# 2. Xác minh Cleaning
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"

# 3. Xác minh Quality Gate GX 1.x
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print('Tín hiệu hoàn thành: Quality check status =', res['success'])"
```

- **Kết quả mong đợi:** 
  - Đã tải 24 bài báo.
  - Clean thành công 24 dòng.
  - Quality check status = True.
- **Kết quả thực tế:** Cả 3 lệnh đều chạy thành công tuyệt đối và in ra đúng tín hiệu.
- **Artifact:** [data/raw/crossref_records.json](file:///d:/K4-L3A-Day10-911Group/data/raw/crossref_records.json), [data/clean/papers_clean.json](file:///d:/K4-L3A-Day10-911Group/data/clean/papers_clean.json), [data/quality/test_quality_report.json](file:///d:/K4-L3A-Day10-911Group/data/quality/test_quality_report.json).

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn cách khởi tạo và lưu trữ ngữ cảnh Great Expectations (GX Context) cho bài lab.
- **Các phương án đã cân nhắc:**
  1. *Phương án A:* Khởi tạo Filesystem Context với thư mục `gx/` trên đĩa cứng lưu trữ config và checkpoint files.
  2. *Phương án B:* Khởi tạo Ephemeral Context (`gx.get_context(mode="ephemeral")`) kết hợp Fluent Pandas Data Source trong bộ nhớ RAM.
- **Phương án đã chọn:** Phương án B (`mode="ephemeral"`).
- **Lý do:** 
  - Loại bỏ hoàn toàn rủi ro xung đột đường dẫn trên Windows/Linux.
  - Không sinh các file tạm `.gx` gây bẩn git repository và khó kiểm soát version control.
  - Tốc độ thực thi chốt kiểm dịch nhanh hơn gấp nhiều lần, hoàn toàn phù hợp với luồng CI/CD và pipeline dữ liệu in-memory.
- **Bằng chứng quyết định phù hợp:** Kết quả chạy `run_data_quality_checks` hoàn thành trong chưa đầy 1 giây, xuất thẳng kết quả validation vào file JSON báo cáo có thể kiểm tra trực tiếp.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```text
  SyntaxError: f-string expression part cannot include a backslash
  ```
  khi chạy lệnh kiểm tra trên Windows PowerShell:
  ```powershell
  python -c "... print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"
  ```
- **Lệnh hoặc bước tái hiện:** Chạy lệnh kiểm tra Bước 3 có chứa `\"` bên trong f-string trên terminal PowerShell.
- **Nguyên nhân gốc:** Parser của PowerShell tự động chèn thêm dấu `\` vào cặp ngoặc kép khiến biểu thức bên trong `{...}` của f-string chứa backslash, vi phạm cú pháp f-string trong Python.
- **Cách xử lý:** Thay đổi cách in không dùng backslash trong f-string, truyền trực tiếp qua tham số của `print()`: `print('Tín hiệu hoàn thành: Quality check status =', res['success'])`.
- **Cách xác minh sau khi sửa:** Lệnh thực thi trả về mã 0 và in ra chính xác: `Tín hiệu hoàn thành: Quality check status = True`.
- **Điều học được:** Khi viết one-liner CLI trên PowerShell của Windows, cần chú ý cơ chế quote escaping khác với bash trên Linux/macOS.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   - Dữ liệu metadata được kéo từ Crossref REST API (hoặc nạp từ snapshot raw nếu offline) $\rightarrow$ parse thành `PaperRecord` $\rightarrow$ lưu bản sao thô vào `crossref_records.json` $\rightarrow$ qua module `cleaning.py` để loại bỏ thẻ HTML/JATS XML rác, khử trùng lặp theo DOI, tính `age_days` $\rightarrow$ ghép thành chuỗi ngữ cảnh chuẩn 5 phần `text_for_embedding` $\rightarrow$ qua chốt kiểm định GX 1.x $\rightarrow$ đưa vào mô hình nhúng `all-MiniLM-L6-v2` $\rightarrow$ lưu trữ embeddings và metadata vào vector collection của ChromaDB.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   - Test set chứa các câu hỏi benchmark cố định cùng với `ground_truth_doc_ids` (DOI của bài báo chứa đáp án chuẩn). Khi truy vấn, hệ thống đo `retrieval_hit_rate` (tỷ lệ câu hỏi mà top-k retrieved docs có chứa DOI chuẩn) và đo `mean_token_f1` (độ trùng khớp giữa câu trả lời sinh ra bởi LLM và ground-truth text).

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - **Quality checks (GX 1.x)**: Kiểm soát tính toàn vẹn cấu trúc và định dạng dữ liệu tĩnh (schema, null, tính duy nhất, độ dài tối thiểu, số lượng dòng).
   - **Freshness monitoring (SLA)**: Kiểm soát chiều kích thời gian động của dữ liệu (`age_days`). Dữ liệu có thể hoàn toàn sạch về cấu trúc nhưng đã lỗi thời (quá 180 ngày). Nếu dữ liệu cũ chiếm > 25%, hệ thống cảnh báo để kích hoạt luồng recrawl/cập nhật.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   - Để đảm bảo tính khách quan và khoa học (Controlled Experiment). Chỉ khi giữ nguyên "thước đo" (bộ câu hỏi và ground-truth), chúng ta mới có thể so sánh định lượng chính xác mức độ suy giảm do dữ liệu rác gây ra và mức độ phục hồi sau khi chạy quy trình sửa chữa dữ liệu.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   - Dựa trên sự phục hồi của các chỉ số trong [data/results/repaired_metrics.json](file:///d:/K4-L3A-Day10-911Group/data/results/repaired_metrics.json) so với `corrupted_metrics.json`: `retrieval_hit_rate` và `mean_token_f1` phải tăng trở lại tiệm cận mức `baseline_metrics.json`.
   - Về mặt dữ liệu: Chốt kiểm tra GX 1.x trên tập repaired phải đạt `success = True`, và bảng đối chiếu 3 trạng thái trong [data/reports/corruption_report.md](file:///d:/K4-L3A-Day10-911Group/data/reports/corruption_report.md) thể hiện rõ ràng biên độ phục hồi.

---

## 8. Phân tích kết quả

### Metrics chính (Dự kiến theo dõi qua 3 pha)

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| :--- | :---: | :---: | :---: | :--- |
| `retrieval_hit_rate` | Cao (~1.0) | Sụt giảm mạnh | Phục hồi cao | Rác trong title/summary làm hỏng khoảng cách cosine trong embedding |
| `mean_token_f1` | Ổn định | Giảm sâu | Phục hồi | Khi retrieval lấy sai tài liệu, LLM sinh đáp án hallucinate làm giảm F1 |
| Quality checks (GX) | `True` | `False` | `True` | Bị chặn lại ở chốt kiểm dịch khi bị tiêm null, duplicate hoặc rỗng |
| Freshness status | `is_fresh = True` | Có thể vi phạm | `True` | Đo lường chính xác tỷ lệ bài quá hạn |

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất
1. **Bảo tồn dữ liệu thô (Raw Preservation & Lineage):** Luôn lưu trữ nguyên vẹn dữ liệu từ API gốc trước khi thực hiện bất kỳ bước biến đổi nào. Đây là chốt an toàn giúp khôi phục hệ thống khi xảy ra sự cố.
2. **Data Observability không chỉ là unit test code:** Dữ liệu có thể gây lỗi âm thầm (silent failure) mà không làm sập chương trình. Cần có chốt kiểm dịch như Great Expectations và giám sát độ tươi (Freshness SLA) để bảo vệ các mô hình downstream.
3. **Chất lượng dữ liệu quyết định chất lượng RAG:** Garbage in, garbage out — chỉ cần một vài thẻ rác hoặc thiếu hụt trường tóm tắt, biểu diễn vector trong ChromaDB sẽ bị sai lệch nghiêm trọng, kéo tụt độ chính xác của câu trả lời.

### Nếu có thêm thời gian
- Tích hợp thêm cơ chế tự động hóa kiểm định Data Drift và schema versioning thông qua pre-commit hook và automated GitHub Actions pipeline.

---

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Dương Minh Hiếu  
**Ngày xác nhận:** 2026-09-25
