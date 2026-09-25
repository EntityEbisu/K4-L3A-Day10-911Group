# Phase 1 - Baseline Data Pipeline & RAG Report

> Sinh tu dong luc: `2026-09-25T09:37:41.583360+00:00`

## 1. Nguon du lieu (Data Lineage)

| Thong tin | Gia tri |
| :--- | :--- |
| Nguon API | Crossref REST API |
| Truy van | `agentic retrieval augmented generation large language model` |
| Bo loc | `from-pub-date:2026-03-29,has-abstract:true` |
| Cach lay du lieu | raw_records_json |
| Raw response | `D:\LabVin\Day10_Lab_Data\K4-L3A-Day10-911Group\data\raw\crossref_response.json` |
| Raw records | `D:\LabVin\Day10_Lab_Data\K4-L3A-Day10-911Group\data\raw\crossref_records.json` |
| Ban ghi tho | 24 |
| Dong sach | 24 |
| Dong bi loai | 0 |
| Collection | `papers-baseline` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |

## 2. Chi so Baseline

| Chi so | Gia tri |
| :--- | :--- |
| So cau hoi | 10 |
| Retrieval Hit Rate | 1.0000 |
| Mean Token F1 | 1.0000 |
| LLM Judge Accuracy | 0.9000 |
| Mean LLM Judge Score | 4.6000 |

## 3. Data Quality Gate (Great Expectations 1.x)

- Ket qua tong: **DAT**
- So expectation dat: 6/6

| Expectation | Cot | Ket qua |
| :--- | :--- | :--- |
| `row_count` | - | dat |
| `paper_id_not_null` | paper_id | dat |
| `paper_id_unique` | paper_id | dat |
| `title_not_null` | title | dat |
| `text_for_embedding_not_null` | text_for_embedding | dat |
| `summary_min_length` | summary | dat |

## 4. Freshness SLA

- Bai moi nhat: 2026-07-22
- Bai cu nhat: 2026-03-28
- So bai qua han (>180 ngay): 1/24
- Ti le qua han: 0.0417 (nguong cho phep 0.25)
- Trang thai: **TUOI (is_fresh=True)**

## 5. Ragas (tuy chon)

- Bo qua: Set RUN_RAGAS=1 to enable the slower Ragas pass.

## 6. Ket luan

- Baseline dat hit rate **1.0000** tren 10 cau hoi benchmark.
- Data quality gate: **dat**; du lieu **con tuoi**.
- Cac chi so nay la moc so sanh (baseline) cho hai pha tiep theo: tien loi du lieu (corruption) va phuc hoi (repair).
