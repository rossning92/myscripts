---
name: pdf-utils
description: Extracts text from PDF documents using pdftotext or OCRmyPDF. Use when the user asks to read, inspect, summarize, search, transcribe, or extract content from a PDF, including scanned PDFs.
compatibility: Requires pdftotext; OCR fallback requires ocrmypdf.
---

# PDF utilities

To read PDF content:

- Using `pdftotext` (fast, requires text layer):
  ```bash
  pdftotext <input_pdf_file> -
  ```
- Using `ocrmypdf` (slower, performs OCR if needed):
  ```bash
  ocrmypdf <input_pdf_file> /dev/null -q --sidecar -
  ```
