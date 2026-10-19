# PramaanLens

Offline screenshot screening for investigators. It outputs **risk flags (HIGH / MEDIUM / LOW)**, never a genuine/fake verdict.
Every flag links to an image region or a metadata field. No generative LLM sits in the evidence path.

## Run (2 steps)
```bash
pip install -r requirements.txt        # also install the Tesseract OCR binary
streamlit run app.py
```

## Layout
| Path | Role |
|---|---|
| `app.py` | Streamlit frontend |
| `backend/custody.py` | SHA-256 seal, SQLite custody log, previous-case hashes |
| `backend/analysis.py` | Metadata, OCR, message order, date logic, edited-region check, reuse detection |
| `report_pdf.py` | PDF report with BSA 2023 s.63 Part A draft |

Use synthetic screenshots only. The original device remains the final check.
