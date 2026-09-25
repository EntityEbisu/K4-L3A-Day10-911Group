# Corruption & Repair - Bao Cao Doi Chieu 3 Trang Thai

> Sinh tu dong luc: `2026-09-25T10:14:05.009377+00:00`

## 1. Bang so sanh chi so

| Chi so | Baseline (sach) | Corrupted (tien loi) | Repaired (phuc hoi) |
| :--- | :--- | :--- | :--- |
| So cau hoi | 10 | 10 | 10 |
| Retrieval Hit Rate | 1.0000 | 0.6000 | 1.0000 |
| Mean Token F1 | 1.0000 | 0.7788 | 1.0000 |
| LLM Judge Accuracy | 0.9000 | 0.8000 | 1.0000 |
| Mean LLM Judge Score | 4.6000 | 4.0000 | 5.0000 |

## 2. Muc do suy giam (Degradation)

| Chi so | Baseline | Corrupted | Chenh lech | Muc giam |
| :--- | :--- | :--- | :--- | :--- |
| Retrieval Hit Rate | 1.0000 | 0.6000 | -0.4000 | -40.0% |
| Mean Token F1 | 1.0000 | 0.7788 | -0.2212 | -22.1% |
| LLM Judge Accuracy | 0.9000 | 0.8000 | -0.1000 | -11.1% |

## 3. Phuc hoi (Repair)

- Retrieval Hit Rate: 1.0000 so voi baseline 1.0000 (+0.0%)
- Mean Token F1: 1.0000 so voi baseline 1.0000 (+0.0%)
- LLM Judge Accuracy: 1.0000 so voi baseline 0.9000 (+11.1%)

## 4. Chat luong du lieu sau tien loi / phuc hoi

### Corrupted

- Quality gate: **khong dat** (4/6)
- So loi phat hien: 2
- Freshness: stale 9/24, is_fresh=Khong

### Repaired

- Quality gate: **dat** (6/6)
- So loi phat hien: 0
- Freshness: stale 1/24, is_fresh=Co

## 5. Ket luan

- Tien loi du lieu lam suy giam ro ret chat luong cau tra loi cua RAG.
- Co che Idempotent Repair phuc hoi du lieu tu raw snapshot, dua chi so tro lai muc xap xi baseline.
