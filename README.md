# ReceiptLens 🔍🧾

**ReceiptLens** is an AI-powered receipt and invoice digitization web application that converts photos and PDFs of receipts into verified structured financial data using **Gemini multimodal structured outputs**.

---

## ✨ Features

1. **Multi-Source Ingestion**:
   - Drag & drop or browse single or multiple receipt images (**JPG, PNG, WebP, PDF**).
   - Direct WebRTC **Camera Capture** with real-time framing guide and snapshot extractor.
   - Built-in **1-Click Demo Receipts** (Indian restaurant with GST/CGST/SGST, grocery mart, taxi invoice, electronics store, calculation mismatch test, and unreadable rejection sample).

2. **Gemini Multimodal Structured Extraction**:
   - Uses strict JSON schema enforcement with Gemini 2.5 Flash / 1.5 Flash.
   - Extracts:
     - `vendor_name`, `date` (normalized to ISO `YYYY-MM-DD`), `currency` (`₹/INR`, `$`, `€`, `£`)
     - `line_items`: `[{name, quantity, unit_price, total}]`
     - `subtotal`, `tax`, `tax_breakdown` (CGST, SGST, IGST, VAT), `tip`, `discount`, `total`
     - `category` (*Food, Travel, Groceries, Utilities, Shopping, Other*)
     - `confidence` score (*0.0 to 1.0*) and list of `unclear_fields`
   - **Rules Enforced**:
     - Returns *only* visible values, uses `null` for missing fields (never guesses).
     - Full support for Indian formats (`₹`, GST, CGST/SGST breakdowns, `dd/mm/yyyy` dates).
     - Retains original language and spelling for item names (e.g., Hindi, regional names, multi-lingual receipts).

3. **Interactive Side-by-Side Review & Verification**:
   - **Left Panel**: Interactive receipt document viewer with **Pan & Drag, Zoom In (+), Zoom Out (-), Fit to Width, 90° Rotation, and Wheel/Touch pinch zoom**.
   - **Right Panel**: Full editable structured data form and table with real-time recalculation, row additions, deletions, and adjustments.

4. **Math Validation & Discrepancy Reconciliation**:
   - Automatically compares `sum(line_items) + tax + tip - discount` against extracted `total`.
   - Flags discrepancies with an alert banner and status badges.
   - 1-Click **Auto-Reconcile** helper to synchronize totals or adjust tax differences.

5. **Analytics Dashboard**:
   - Key KPI Summary Cards: Total Spend, Total Receipts, Average Ticket Size, Discrepancy Flags.
   - **Monthly Spending by Category**: Interactive stacked bar chart (Chart.js).
   - **Category Distribution**: Interactive donut chart.
   - **Top Vendors Leaderboard**: Ranked by total spending and visit counts.

6. **Export & Storage**:
   - **CSV Export** (Flattened line-items or summary rows).
   - **JSON Export** (Full structured hierarchical data).
   - Individual receipt downloads or bulk export.
   - Persistent **SQLite** storage (`receipts.db`).

7. **Friendly Error Recovery**:
   - Detects blurry, out-of-focus, or non-receipt images, displaying a human-friendly explanation and guidance to retake or upload clearer images.

8. **Secure Architecture**:
   - Keeps API keys strictly on the server backend (`.env`), never exposed to client code.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- Installed packages from `requirements.txt`

### 2. Installation
```bash
pip install -r requirements.txt
```

### 3. Launching the App
```bash
python3 server.py
```
Open your browser at `http://localhost:8000`.

### 4. Setting your Gemini API Key
- Enter your key in the UI under **Settings** (`AIzaSy...`), or add `GEMINI_API_KEY=your_key_here` to `.env`.
- You can get a free key from [Google AI Studio](https://aistudio.google.com/app/apikey).
