# PramaanLens

## Problem

Chat screenshots are easy to forward and difficult to verify from the image alone. Reviewers need a practical way to record a file's fingerprint, surface details worth checking, and preserve a simple local custody trail.

## Solution

PramaanLens is an offline Streamlit tool for **screening chat screenshots**. It seals each uploaded file with SHA-256, records local custody events in SQLite, and reports explainable HIGH / MEDIUM / LOW risk flags with verification steps. It does not decide whether a screenshot is genuine or fake.

No generative LLM is used in the evidence path. The original conversation on the source device remains the important verification step.

## Key Features

- Local SHA-256 file fingerprint and SQLite custody log.
- Rule-based checks for image metadata, OCR text, message order, date logic, compression differences, and perceptual-hash similarity to earlier cases.
- Risk flags linked to image regions or metadata fields, with suggested follow-up actions.
- Optional, separate **ML assist (experimental)** card. It does not override or change rule-based flags.
- Bundled synthetic screenshots for safely trying the analysis workflow.
- PDF report with a BSA 2023 s.63 Part A draft for review.

## Technologies

Python, Streamlit, Pillow, Tesseract OCR, OpenCV, imagehash, SQLite, scikit-learn, joblib, and ReportLab. Plus Jakarta Sans is bundled locally under its SIL Open Font License.

## Layout

| Path | Purpose |
| --- | --- |
| `app.py` | Streamlit interface and local analysis flow |
| `backend/analysis.py` | Rule-based screenshot checks and numeric features |
| `backend/custody.py` | SHA-256 sealing and SQLite custody log |
| `backend/ml_model.py` | Optional experimental classifier |
| `backend/report_pdf.py` | PDF report generation |
| `backend/train_model.py` | Synthetic-data generation and model training |
| `assets/` | Local styles, empty-state animation, fonts, and synthetic samples |
| `models/model.joblib` | Bundled synthetic-data model; optional at runtime |
| `docs/` | Sample report and screenshots placeholder |
| `tests/` | Unit tests for analysis, model, and synthetic training |

## Target Users

Investigators, legal-support teams, journalists, and educators who need a first-pass way to organize screenshot verification. PramaanLens is a triage aid, not a forensic certification tool.

## How to Run

Use Python with the packages in `requirements.txt` and install the Tesseract OCR executable separately. For Debian or Ubuntu:

```bash
sudo apt install tesseract-ocr
python -m pip install -r requirements.txt
streamlit run app.py
```

In the sidebar, upload a PNG, JPEG, or WebP screenshot and select **Seal and analyse**. Or choose one of the bundled synthetic examples and select **Try sample**. All processing is local; the SQLite custody database is stored under `data/`.

To regenerate the synthetic training set, evaluate a model on a held-out split, and save `models/model.joblib`:

```bash
python -m backend.train_model
```

The script also regenerates the synthetic sample images in `assets/samples/`. Its printed precision and recall describe only a held-out split of generated data.

To regenerate the bundled PDF example:

```bash
python -m backend.report_pdf
```

The report is written to `docs/sample_report.pdf`.

## Limitations

- A missing metadata field is common and is not, by itself, evidence of editing. OCR may miss or misread text; date and time formats vary; and compression-based checks are noisy on screenshots.
- Perceptual similarity is a prompt to compare earlier files, not proof that they are related.
- The SHA-256 fingerprint detects changes to the file after it is received. The local SQLite custody log is not a tamper-proof or digitally signed evidence system.
- Automated analysis can produce false positives and false negatives. Verify findings against the original chat and device.
- The PDF's BSA 2023 s.63 Part A content is a draft only. It is not legal advice, a certificate, or a substitute for review by a qualified person.
- The tool is designed for local use and does not upload evidence. Protect the device and local database according to your organization's handling procedures.

## ML Assist (Experimental)

The optional scikit-learn classifier consumes numeric signals already calculated by the rule-based analyzer: per-check flag counts, OCR confidence, an edited-region score, date and message-order anomaly counts, and nearest perceptual-hash distance. It displays a risk label and the model's class probability in its own card; it never replaces the rule-based flags.

Training examples are generated with Pillow from synthetic chat-style images and known synthetic scenarios. The train/test split, reported metrics, and model are **synthetic-data based only**. The displayed probability is not calibrated for real screenshots, and performance on synthetic examples is not evidence of real-world accuracy. If `models/model.joblib` is missing or cannot be loaded, the rest of the app continues to work and the ML card explains how to train the optional model.

The repository includes a small `models/model.joblib` generated by this training script so the experimental card is available immediately after setup. Run `python -m backend.train_model` to regenerate it locally.
