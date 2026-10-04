import os
import json
import sqlite3
import base64
import re
import io
import csv
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import requests
from PIL import Image

# Load environment variables
load_dotenv()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_DIR, "static")
DB_PATH = os.path.join(APP_DIR, "receipts.db")

app = FastAPI(title="ReceiptLens API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Database Setup & Migrations
# -----------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            filename TEXT,
            image_data TEXT,
            mime_type TEXT,
            vendor_name TEXT,
            vendor_address TEXT,
            vendor_phone TEXT,
            date TEXT,
            currency TEXT,
            currency_symbol TEXT,
            category TEXT,
            subtotal REAL,
            tax REAL,
            tax_breakdown TEXT,
            tip REAL,
            discount REAL,
            total REAL,
            payment_method TEXT,
            confidence REAL,
            unclear_fields TEXT,
            is_valid_receipt INTEGER DEFAULT 1,
            rejection_reason TEXT,
            validation_status TEXT,
            validation_discrepancy REAL,
            validation_message TEXT,
            notes TEXT,
            raw_gemini_response TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS line_items (
            id TEXT PRIMARY KEY,
            receipt_id TEXT NOT NULL,
            name TEXT NOT NULL,
            quantity REAL,
            unit_price REAL,
            total REAL,
            item_order INTEGER DEFAULT 0,
            FOREIGN KEY (receipt_id) REFERENCES receipts (id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

init_db()

# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------
class LineItemModel(BaseModel):
    id: Optional[str] = None
    name: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total: Optional[float] = None

class TaxBreakdownModel(BaseModel):
    cgst: Optional[float] = None
    sgst: Optional[float] = None
    igst: Optional[float] = None
    vat: Optional[float] = None

class ReceiptExtractResponse(BaseModel):
    is_receipt: bool = Field(description="False if image is not a receipt, invoice, or bill, or if totally unreadable")
    rejection_reason: Optional[str] = Field(default=None, description="Explanation if image is blurry, corrupted, or not a receipt")
    vendor_name: Optional[str] = Field(default=None, description="Name of the store, restaurant, or vendor")
    vendor_address: Optional[str] = Field(default=None, description="Address if present")
    vendor_phone: Optional[str] = Field(default=None, description="Phone number if present")
    date: Optional[str] = Field(default=None, description="Date in YYYY-MM-DD format")
    currency: Optional[str] = Field(default="INR", description="Currency code (e.g., INR, USD, EUR, GBP)")
    currency_symbol: Optional[str] = Field(default="₹", description="Currency symbol (e.g., ₹, $, €, £)")
    line_items: List[LineItemModel] = Field(default_factory=list, description="Extracted individual items")
    subtotal: Optional[float] = Field(default=None, description="Subtotal before taxes/discounts/tips")
    tax: Optional[float] = Field(default=None, description="Total tax amount (sum of GST/CGST/SGST/VAT)")
    tax_breakdown: Optional[TaxBreakdownModel] = Field(default=None, description="Breakdown of taxes like CGST, SGST, IGST")
    tip: Optional[float] = Field(default=None, description="Tip or gratuity amount")
    discount: Optional[float] = Field(default=None, description="Discount amount if any")
    total: Optional[float] = Field(default=None, description="Grand final total paid or payable")
    payment_method: Optional[str] = Field(default=None, description="Cash, Card, UPI, Wallet, etc.")
    category: str = Field(default="Other", description="One of: Food, Travel, Groceries, Utilities, Shopping, Other")
    confidence: float = Field(default=0.9, description="Confidence score between 0.0 and 1.0")
    unclear_fields: List[str] = Field(default_factory=list, description="List of fields that were blurry, missing or uncertain")
    notes: Optional[str] = Field(default=None, description="Any invoice number, GSTIN, or additional details")

class ReceiptSaveRequest(BaseModel):
    id: Optional[str] = None
    filename: Optional[str] = "receipt.jpg"
    image_data: Optional[str] = None
    mime_type: Optional[str] = "image/jpeg"
    vendor_name: Optional[str] = None
    vendor_address: Optional[str] = None
    vendor_phone: Optional[str] = None
    date: Optional[str] = None
    currency: Optional[str] = "INR"
    currency_symbol: Optional[str] = "₹"
    category: Optional[str] = "Other"
    line_items: List[LineItemModel] = []
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    tax_breakdown: Optional[Dict[str, Any]] = None
    tip: Optional[float] = None
    discount: Optional[float] = None
    total: Optional[float] = None
    payment_method: Optional[str] = None
    confidence: Optional[float] = 1.0
    unclear_fields: List[str] = []
    is_valid_receipt: bool = True
    rejection_reason: Optional[str] = None
    notes: Optional[str] = None

class SetApiKeyRequest(BaseModel):
    api_key: str

# -----------------------------------------------------------------------------
# Validation Helper
# -----------------------------------------------------------------------------
def validate_receipt_math(line_items: List[Dict[str, Any]], tax: Optional[float], tip: Optional[float], discount: Optional[float], total: Optional[float]) -> Dict[str, Any]:
    tax_val = tax or 0.0
    tip_val = tip or 0.0
    disc_val = discount or 0.0
    
    items_sum = sum((item.get("total") or 0.0) for item in line_items)
    
    if total is None:
        return {
            "status": "warning",
            "discrepancy": 0.0,
            "message": "Total amount is missing on this receipt."
        }
    
    # If there are line items with prices
    if line_items and any((item.get("total") or 0.0) > 0 for item in line_items):
        expected_total = items_sum + tax_val + tip_val - disc_val
        discrepancy = round(abs(expected_total - total), 2)
        
        # Tolerance of 0.05 for rounding differences
        if discrepancy <= 0.05:
            return {
                "status": "valid",
                "discrepancy": 0.0,
                "message": "Sum of line items + tax + tip matches total exactly."
            }
        else:
            return {
                "status": "flagged",
                "discrepancy": discrepancy,
                "items_sum": round(items_sum, 2),
                "expected_total": round(expected_total, 2),
                "actual_total": round(total, 2),
                "message": f"Calculation Mismatch: Sum of items ({items_sum:.2f}) + Tax ({tax_val:.2f}) + Tip ({tip_val:.2f}) = {expected_total:.2f}, but Total is {total:.2f} (Discrepancy: {discrepancy:.2f})"
            }
    
    return {
        "status": "valid",
        "discrepancy": 0.0,
        "message": "Total verified."
    }

# -----------------------------------------------------------------------------
# Gemini Extraction Service
# -----------------------------------------------------------------------------
GEMINI_EXTRACTION_PROMPT = """
You are an expert AI receipt and invoice document parser specialized in extracting structured data with high precision.

Strict extraction instructions:
1. Return ONLY values that are clearly visible on the receipt or invoice. Use null for any field that is missing or not visible. NEVER make up, invent, or guess any value.
2. Support Indian formats:
   - Indian Rupee (₹ or INR or Rs.)
   - GST, CGST, SGST, IGST tax breakdowns
   - dd/mm/yyyy or dd-mmm-yyyy dates: normalize all dates to standard ISO "YYYY-MM-DD" format.
3. Keep the original language and spelling of all item names (e.g. Hindi, regional languages, or English item names like "Paneer Butter Masala", "Masala Dosa", "Filter Coffee").
4. For each line item:
   - name: full item name
   - quantity: number or float (null if not specified)
   - unit_price: price per unit (null if not specified)
   - total: total line item price (null if not specified)
5. Categories: strictly classify into one of: ["Food", "Travel", "Groceries", "Utilities", "Shopping", "Other"].
6. Confidence: evaluate your confidence score between 0.0 (unreadable) and 1.0 (perfect clarity).
7. unclear_fields: provide an array of field names that were blurry, cut-off, faded, or ambiguous.
8. Blurry or Non-Receipt images:
   - If the image is not a financial receipt/invoice/bill (e.g., photo of a person, animal, landscape, random document, blank page) OR is completely unreadable/blurry:
     set `is_receipt: false` and set `rejection_reason` to a clear, friendly human explanation of why it cannot be processed.

Output must be strictly valid JSON matching the requested schema.
"""

GEMINI_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "is_receipt": {"type": "boolean", "description": "Whether the image is a valid legible receipt/invoice"},
        "rejection_reason": {"type": ["string", "null"], "description": "Friendly explanation if not a valid receipt"},
        "vendor_name": {"type": ["string", "null"], "description": "Name of store, merchant or vendor"},
        "vendor_address": {"type": ["string", "null"]},
        "vendor_phone": {"type": ["string", "null"]},
        "date": {"type": ["string", "null"], "description": "YYYY-MM-DD normalized date"},
        "currency": {"type": ["string", "null"], "description": "INR, USD, EUR, GBP, etc."},
        "currency_symbol": {"type": ["string", "null"], "description": "₹, $, €, £, etc."},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": ["number", "null"]},
                    "unit_price": {"type": ["number", "null"]},
                    "total": {"type": ["number", "null"]}
                },
                "required": ["name"]
            }
        },
        "subtotal": {"type": ["number", "null"]},
        "tax": {"type": ["number", "null"]},
        "tax_breakdown": {
            "type": ["object", "null"],
            "properties": {
                "cgst": {"type": ["number", "null"]},
                "sgst": {"type": ["number", "null"]},
                "igst": {"type": ["number", "null"]},
                "vat": {"type": ["number", "null"]}
            }
        },
        "tip": {"type": ["number", "null"]},
        "discount": {"type": ["number", "null"]},
        "total": {"type": ["number", "null"]},
        "payment_method": {"type": ["string", "null"]},
        "category": {
            "type": "string",
            "enum": ["Food", "Travel", "Groceries", "Utilities", "Shopping", "Other"]
        },
        "confidence": {"type": "number"},
        "unclear_fields": {
            "type": "array",
            "items": {"type": "string"}
        },
        "notes": {"type": ["string", "null"]}
    },
    "required": ["is_receipt", "category", "confidence", "line_items"]
}

def extract_with_gemini(image_bytes: bytes, mime_type: str, api_key: str) -> Dict[str, Any]:
    """Calls Gemini with structured JSON output schema."""
    # Preferred models in order
    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    
    b64_data = base64.b64encode(image_bytes).decode("utf-8")
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": GEMINI_EXTRACTION_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_data
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json",
            "response_schema": GEMINI_JSON_SCHEMA
        }
    }
    
    last_error = None
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=45)
            if resp.status_code == 200:
                result_json = resp.json()
                text_content = result_json["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text_content)
                return parsed
            else:
                last_error = f"Gemini API error ({resp.status_code}): {resp.text}"
        except Exception as e:
            last_error = str(e)
            continue
            
    raise Exception(f"Failed to extract with Gemini: {last_error}")

# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/config")
def get_config():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    return {
        "has_api_key": bool(api_key.strip()),
        "key_preview": f"...{api_key[-4:]}" if len(api_key) > 8 else ("Set" if api_key else "Not set")
    }

@app.post("/api/config/key")
def update_api_key(req: SetApiKeyRequest):
    key = req.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    
    os.environ["GEMINI_API_KEY"] = key
    
    # Also write/update to .env file
    env_path = os.path.join(APP_DIR, ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith("GEMINI_API_KEY="):
            new_lines.append(f"GEMINI_API_KEY={key}\n")
            updated = True
        else:
            new_lines.append(line)
            
    if not updated:
        new_lines.append(f"GEMINI_API_KEY={key}\n")
        
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
        
    return {"status": "success", "message": "API key successfully updated"}

@app.post("/api/extract")
async def extract_receipt(file: UploadFile = File(...)):
    """Receives receipt image or PDF and extracts structured data."""
    contents = await file.read()
    mime_type = file.content_type or "image/jpeg"
    
    # If generic octet-stream, guess from filename
    if mime_type == "application/octet-stream" or not mime_type:
        filename_lower = file.filename.lower()
        if filename_lower.endswith(".png"):
            mime_type = "image/png"
        elif filename_lower.endswith(".pdf"):
            mime_type = "application/pdf"
        elif filename_lower.endswith(".webp"):
            mime_type = "image/webp"
        else:
            mime_type = "image/jpeg"
            
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="Gemini API key is not configured. Please set your Gemini API key in Settings."
        )
    
    try:
        extraction = extract_with_gemini(contents, mime_type, api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # Store base64 data preview
    b64_img = f"data:{mime_type};base64,{base64.b64encode(contents).decode('utf-8')}"
    
    # Calculate math validation
    line_items_dict = extraction.get("line_items", [])
    validation = validate_receipt_math(
        line_items=line_items_dict,
        tax=extraction.get("tax"),
        tip=extraction.get("tip"),
        discount=extraction.get("discount"),
        total=extraction.get("total")
    )
    
    receipt_id = f"rcpt_{int(datetime.now().timestamp()*1000)}"
    
    return {
        "id": receipt_id,
        "filename": file.filename,
        "mime_type": mime_type,
        "image_data": b64_img,
        "extracted_data": extraction,
        "validation": validation
    }

@app.post("/api/receipts")
def save_receipt(req: ReceiptSaveRequest):
    receipt_id = req.id or f"rcpt_{int(datetime.now().timestamp()*1000)}"
    conn = get_db()
    cursor = conn.cursor()
    
    # Calculate validation
    items_dicts = [item.model_dump() for item in req.line_items]
    val = validate_receipt_math(
        line_items=items_dicts,
        tax=req.tax,
        tip=req.tip,
        discount=req.discount,
        total=req.total
    )
    
    now_str = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT OR REPLACE INTO receipts (
            id, created_at, filename, image_data, mime_type,
            vendor_name, vendor_address, vendor_phone, date,
            currency, currency_symbol, category, subtotal, tax,
            tax_breakdown, tip, discount, total, payment_method,
            confidence, unclear_fields, is_valid_receipt,
            rejection_reason, validation_status, validation_discrepancy,
            validation_message, notes, raw_gemini_response
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        receipt_id,
        now_str,
        req.filename,
        req.image_data,
        req.mime_type,
        req.vendor_name,
        req.vendor_address,
        req.vendor_phone,
        req.date,
        req.currency or "INR",
        req.currency_symbol or "₹",
        req.category or "Other",
        req.subtotal,
        req.tax,
        json.dumps(req.tax_breakdown) if req.tax_breakdown else None,
        req.tip,
        req.discount,
        req.total,
        req.payment_method,
        req.confidence,
        json.dumps(req.unclear_fields or []),
        1 if req.is_valid_receipt else 0,
        req.rejection_reason,
        val["status"],
        val.get("discrepancy", 0.0),
        val.get("message", ""),
        req.notes,
        json.dumps(req.model_dump())
    ))
    
    # Clear and re-insert line items
    cursor.execute("DELETE FROM line_items WHERE receipt_id = ?", (receipt_id,))
    for i, item in enumerate(req.line_items):
        item_id = item.id or f"item_{receipt_id}_{i}"
        cursor.execute("""
            INSERT INTO line_items (id, receipt_id, name, quantity, unit_price, total, item_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (item_id, receipt_id, item.name, item.quantity, item.unit_price, item.total, i))
        
    conn.commit()
    conn.close()
    
    return {"status": "saved", "id": receipt_id, "validation": val}

@app.get("/api/receipts")
def list_receipts(
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None
):
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM receipts WHERE 1=1"
    params = []
    
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    if status and status != "All":
        query += " AND validation_status = ?"
        params.append(status)
    if search:
        query += " AND (vendor_name LIKE ? OR notes LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
        
    query += " ORDER BY COALESCE(date, created_at) DESC, created_at DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    receipts_list = []
    for r in rows:
        r_dict = dict(r)
        r_id = r_dict["id"]
        
        # Load line items
        cursor.execute("SELECT * FROM line_items WHERE receipt_id = ? ORDER BY item_order ASC", (r_id,))
        items = [dict(item) for item in cursor.fetchall()]
        r_dict["line_items"] = items
        
        # Parse JSON fields
        if r_dict.get("tax_breakdown"):
            try:
                r_dict["tax_breakdown"] = json.loads(r_dict["tax_breakdown"])
            except:
                pass
        if r_dict.get("unclear_fields"):
            try:
                r_dict["unclear_fields"] = json.loads(r_dict["unclear_fields"])
            except:
                r_dict["unclear_fields"] = []
                
        receipts_list.append(r_dict)
        
    conn.close()
    return receipts_list

@app.get("/api/receipts/{receipt_id}")
def get_receipt(receipt_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Receipt not found")
        
    r_dict = dict(row)
    cursor.execute("SELECT * FROM line_items WHERE receipt_id = ? ORDER BY item_order ASC", (receipt_id,))
    r_dict["line_items"] = [dict(item) for item in cursor.fetchall()]
    
    if r_dict.get("tax_breakdown"):
        try:
            r_dict["tax_breakdown"] = json.loads(r_dict["tax_breakdown"])
        except:
            pass
    if r_dict.get("unclear_fields"):
        try:
            r_dict["unclear_fields"] = json.loads(r_dict["unclear_fields"])
        except:
            r_dict["unclear_fields"] = []
            
    conn.close()
    return r_dict

@app.delete("/api/receipts/{receipt_id}")
def delete_receipt(receipt_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM line_items WHERE receipt_id = ?", (receipt_id,))
    cursor.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "id": receipt_id}

@app.get("/api/stats")
def get_dashboard_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    # Total receipts, total spend, flagged count
    cursor.execute("""
        SELECT 
            COUNT(*) as total_receipts,
            COALESCE(SUM(total), 0) as total_spend,
            COALESCE(AVG(total), 0) as avg_spend,
            SUM(CASE WHEN validation_status = 'flagged' THEN 1 ELSE 0 END) as flagged_count
        FROM receipts
        WHERE is_valid_receipt = 1
    """)
    overview = dict(cursor.fetchone())
    
    # Monthly spending by category
    cursor.execute("""
        SELECT 
            SUBSTR(COALESCE(date, created_at), 1, 7) as month_key,
            category,
            SUM(total) as amount,
            COUNT(*) as count
        FROM receipts
        WHERE is_valid_receipt = 1 AND COALESCE(date, created_at) IS NOT NULL
        GROUP BY month_key, category
        ORDER BY month_key ASC
    """)
    monthly_data = [dict(r) for r in cursor.fetchall()]
    
    # Spending by category overall
    cursor.execute("""
        SELECT 
            category,
            SUM(total) as total_amount,
            COUNT(*) as receipt_count
        FROM receipts
        WHERE is_valid_receipt = 1
        GROUP BY category
        ORDER BY total_amount DESC
    """)
    category_data = [dict(r) for r in cursor.fetchall()]
    
    # Top vendors
    cursor.execute("""
        SELECT 
            COALESCE(vendor_name, 'Unknown Vendor') as vendor,
            SUM(total) as total_spend,
            COUNT(*) as visit_count
        FROM receipts
        WHERE is_valid_receipt = 1
        GROUP BY vendor
        ORDER BY total_spend DESC
        LIMIT 6
    """)
    top_vendors = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return {
        "overview": overview,
        "monthly_spending": monthly_data,
        "category_spending": category_data,
        "top_vendors": top_vendors
    }

@app.get("/api/export/csv")
def export_csv(mode: str = Query("flattened", description="flattened or summary")):
    conn = get_db()
    cursor = conn.cursor()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    if mode == "flattened":
        # Each line item has a row
        writer.writerow([
            "Receipt ID", "Date", "Vendor", "Category", "Currency",
            "Item Name", "Quantity", "Unit Price", "Line Total",
            "Subtotal", "Tax", "Tip", "Discount", "Grand Total",
            "Payment Method", "Status", "Validation Message"
        ])
        
        cursor.execute("""
            SELECT r.id, r.date, r.vendor_name, r.category, r.currency,
                   l.name as item_name, l.quantity, l.unit_price, l.total as item_total,
                   r.subtotal, r.tax, r.tip, r.discount, r.total as grand_total,
                   r.payment_method, r.validation_status, r.validation_message
            FROM receipts r
            LEFT JOIN line_items l ON r.id = l.receipt_id
            ORDER BY r.date DESC, r.id, l.item_order ASC
        """)
        for row in cursor.fetchall():
            writer.writerow(list(row))
    else:
        # One row per receipt
        writer.writerow([
            "Receipt ID", "Date", "Vendor", "Category", "Currency",
            "Subtotal", "Tax", "Tip", "Discount", "Total",
            "Payment Method", "Items Count", "Confidence", "Validation Status", "Notes"
        ])
        cursor.execute("""
            SELECT r.id, r.date, r.vendor_name, r.category, r.currency,
                   r.subtotal, r.tax, r.tip, r.discount, r.total,
                   r.payment_method, COUNT(l.id) as items_count, r.confidence,
                   r.validation_status, r.notes
            FROM receipts r
            LEFT JOIN line_items l ON r.id = l.receipt_id
            GROUP BY r.id
            ORDER BY r.date DESC
        """)
        for row in cursor.fetchall():
            writer.writerow(list(row))
            
    conn.close()
    
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=receiptlens_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )

@app.get("/api/export/json")
def export_json():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM receipts ORDER BY date DESC")
    receipts_list = []
    for r in cursor.fetchall():
        r_dict = dict(r)
        r_id = r_dict["id"]
        cursor.execute("SELECT name, quantity, unit_price, total FROM line_items WHERE receipt_id = ? ORDER BY item_order ASC", (r_id,))
        r_dict["line_items"] = [dict(item) for item in cursor.fetchall()]
        if r_dict.get("tax_breakdown"):
            try:
                r_dict["tax_breakdown"] = json.loads(r_dict["tax_breakdown"])
            except:
                pass
        if r_dict.get("unclear_fields"):
            try:
                r_dict["unclear_fields"] = json.loads(r_dict["unclear_fields"])
            except:
                pass
        receipts_list.append(r_dict)
    conn.close()
    
    return Response(
        content=json.dumps(receipts_list, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=receiptlens_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"}
    )

# -----------------------------------------------------------------------------
# Demo / Sample Receipts Generator & Loader
# -----------------------------------------------------------------------------
DEMO_SAMPLES = [
    {
        "id": "demo_indian_bhavan",
        "vendor_name": "Saravana Bhavan Pure Veg",
        "vendor_address": "Connaught Place, New Delhi, India",
        "vendor_phone": "+91 11 2341 7890",
        "date": "2026-09-28",
        "currency": "INR",
        "currency_symbol": "₹",
        "category": "Food",
        "payment_method": "UPI / GPay",
        "subtotal": 850.00,
        "tax": 42.50,
        "tax_breakdown": {
            "cgst": 21.25,
            "sgst": 21.25,
            "igst": 0.0,
            "vat": 0.0
        },
        "tip": 50.00,
        "discount": 0.0,
        "total": 942.50,
        "confidence": 0.98,
        "unclear_fields": [],
        "is_valid_receipt": True,
        "notes": "GSTIN: 07AAAAA0000A1Z5 | Table No: 14 | Bill #SB-9842",
        "line_items": [
            {"name": "Masala Dosa Special", "quantity": 2, "unit_price": 160.00, "total": 320.00},
            {"name": "Paneer Butter Masala", "quantity": 1, "unit_price": 280.00, "total": 280.00},
            {"name": "Butter Naan (Basket)", "quantity": 3, "unit_price": 50.00, "total": 150.00},
            {"name": "South Indian Filter Coffee", "quantity": 2, "unit_price": 50.00, "total": 100.00}
        ]
    },
    {
        "id": "demo_supermarket_groceries",
        "vendor_name": "Nature's Basket Organic Mart",
        "vendor_address": "Indiranagar 100ft Road, Bengaluru",
        "vendor_phone": "+91 80 4123 5566",
        "date": "2026-10-02",
        "currency": "INR",
        "currency_symbol": "₹",
        "category": "Groceries",
        "payment_method": "Credit Card (HDFC)",
        "subtotal": 1420.00,
        "tax": 71.00,
        "tax_breakdown": {
            "cgst": 35.50,
            "sgst": 35.50,
            "igst": 0.0,
            "vat": 0.0
        },
        "tip": 0.0,
        "discount": 50.00,
        "total": 1441.00,
        "confidence": 0.95,
        "unclear_fields": [],
        "is_valid_receipt": True,
        "notes": "Invoice #NB-4819 | Member ID: NB-7721",
        "line_items": [
            {"name": "Aashirvaad Shudh Chakki Atta 5kg", "quantity": 1, "unit_price": 295.00, "total": 295.00},
            {"name": "Organic Alphonso Mango Pulp 850g", "quantity": 2, "unit_price": 225.00, "total": 450.00},
            {"name": "Fortune Sunlite Sunflower Oil 1L", "quantity": 2, "unit_price": 160.00, "total": 320.00},
            {"name": "Amul Pasteurised Butter 500g", "quantity": 1, "unit_price": 275.00, "total": 275.00},
            {"name": "Broccoli Exotic 500g", "quantity": 1, "unit_price": 80.00, "total": 80.00}
        ]
    },
    {
        "id": "demo_travel_uber",
        "vendor_name": "Uber India Systems Pvt Ltd",
        "vendor_address": "Mumbai International Airport Terminal 2",
        "vendor_phone": None,
        "date": "2026-10-03",
        "currency": "INR",
        "currency_symbol": "₹",
        "category": "Travel",
        "payment_method": "Amazon Pay",
        "subtotal": 680.00,
        "tax": 34.00,
        "tax_breakdown": {
            "cgst": 17.00,
            "sgst": 17.00,
            "igst": 0.0,
            "vat": 0.0
        },
        "tip": 40.00,
        "discount": 0.0,
        "total": 754.00,
        "confidence": 0.99,
        "unclear_fields": [],
        "is_valid_receipt": True,
        "notes": "Trip ID: 9481a8-uber-premier | Driver: Rajesh Kumar",
        "line_items": [
            {"name": "Uber Premier Airport Drop (28.4 km)", "quantity": 1, "unit_price": 580.00, "total": 580.00},
            {"name": "Airport Toll & Parking Surcharge", "quantity": 1, "unit_price": 100.00, "total": 100.00}
        ]
    },
    {
        "id": "demo_electronics_gadget",
        "vendor_name": "Croma Digital Superstore",
        "vendor_address": "Phoenix Marketcity, Kurla, Mumbai",
        "vendor_phone": "+91 22 6180 1200",
        "date": "2026-09-15",
        "currency": "INR",
        "currency_symbol": "₹",
        "category": "Shopping",
        "payment_method": "Debit Card (ICICI)",
        "subtotal": 4200.00,
        "tax": 756.00,
        "tax_breakdown": {
            "cgst": 378.00,
            "sgst": 378.00,
            "igst": 0.0,
            "vat": 0.0
        },
        "tip": 0.0,
        "discount": 200.00,
        "total": 4756.00,
        "confidence": 0.94,
        "unclear_fields": ["warranty_serial"],
        "is_valid_receipt": True,
        "notes": "Tax Invoice CR-9912 | GSTIN: 27AACCC1122D1Z0",
        "line_items": [
            {"name": "SanDisk 1TB Extreme Portable SSD", "quantity": 1, "unit_price": 3499.00, "total": 3499.00},
            {"name": "Anker 65W GaN Fast Charger USB-C", "quantity": 1, "unit_price": 701.00, "total": 701.00}
        ]
    },
    {
        "id": "demo_mismatch_receipt",
        "vendor_name": "Cafe Mocha Deluxe",
        "vendor_address": "Bandra West, Mumbai",
        "vendor_phone": "+91 22 2640 9988",
        "date": "2026-10-04",
        "currency": "INR",
        "currency_symbol": "₹",
        "category": "Food",
        "payment_method": "Cash",
        "subtotal": 520.00,
        "tax": 26.00,
        "tax_breakdown": {"cgst": 13.00, "sgst": 13.00},
        "tip": 20.00,
        "discount": 0.0,
        "total": 620.00,  # Intentional discrepancy to test validation (520+26+20 = 566, total says 620)
        "confidence": 0.88,
        "unclear_fields": ["handwritten_tip"],
        "is_valid_receipt": True,
        "notes": "Table 04 | Handwritten addition on paper slip",
        "line_items": [
            {"name": "Hazelnut Cappuccino", "quantity": 2, "unit_price": 180.00, "total": 360.00},
            {"name": "Belgian Chocolate Croissant", "quantity": 1, "unit_price": 160.00, "total": 160.00}
        ]
    },
    {
        "id": "demo_blurry_rejection",
        "vendor_name": None,
        "vendor_address": None,
        "vendor_phone": None,
        "date": None,
        "currency": "INR",
        "currency_symbol": "₹",
        "category": "Other",
        "payment_method": None,
        "subtotal": None,
        "tax": None,
        "tax_breakdown": None,
        "tip": None,
        "discount": None,
        "total": None,
        "confidence": 0.15,
        "unclear_fields": ["vendor", "date", "line_items", "tax", "total"],
        "is_valid_receipt": False,
        "rejection_reason": "Image is extremely out of focus, shaky, and text is unreadable. Please retake the photo in good lighting with the receipt placed flat on a dark surface.",
        "notes": "Unreadable input image sample",
        "line_items": []
    }
]

@app.get("/api/samples")
def get_sample_receipts():
    return DEMO_SAMPLES

@app.post("/api/samples/seed")
def seed_sample_receipts():
    """Seeds database with sample receipts if empty."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM receipts")
    count = cursor.fetchone()[0]
    
    if count == 0:
        for sample in DEMO_SAMPLES:
            if sample.get("is_valid_receipt", True):
                val = validate_receipt_math(
                    line_items=sample.get("line_items", []),
                    tax=sample.get("tax"),
                    tip=sample.get("tip"),
                    discount=sample.get("discount"),
                    total=sample.get("total")
                )
                svg_path = f"/samples/{sample['id']}.svg"
                cursor.execute("""
                    INSERT OR REPLACE INTO receipts (
                        id, created_at, filename, image_data, mime_type,
                        vendor_name, vendor_address, vendor_phone, date,
                        currency, currency_symbol, category, subtotal, tax,
                        tax_breakdown, tip, discount, total, payment_method,
                        confidence, unclear_fields, is_valid_receipt,
                        rejection_reason, validation_status, validation_discrepancy,
                        validation_message, notes, raw_gemini_response
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    sample["id"],
                    datetime.now().isoformat(),
                    f"{sample['id']}.svg",
                    svg_path,
                    "image/svg+xml",
                    sample.get("vendor_name"),
                    sample.get("vendor_address"),
                    sample.get("vendor_phone"),
                    sample.get("date"),
                    sample.get("currency", "INR"),
                    sample.get("currency_symbol", "₹"),
                    sample.get("category", "Other"),
                    sample.get("subtotal"),
                    sample.get("tax"),
                    json.dumps(sample.get("tax_breakdown")) if sample.get("tax_breakdown") else None,
                    sample.get("tip"),
                    sample.get("discount"),
                    sample.get("total"),
                    sample.get("payment_method"),
                    sample.get("confidence", 0.9),
                    json.dumps(sample.get("unclear_fields", [])),
                    1 if sample.get("is_valid_receipt", True) else 0,
                    sample.get("rejection_reason"),
                    val["status"],
                    val.get("discrepancy", 0.0),
                    val.get("message", ""),
                    sample.get("notes"),
                    json.dumps(sample)
                ))
                
                cursor.execute("DELETE FROM line_items WHERE receipt_id = ?", (sample["id"],))
                for idx, item in enumerate(sample.get("line_items", [])):
                    cursor.execute("""
                        INSERT INTO line_items (id, receipt_id, name, quantity, unit_price, total, item_order)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (f"item_{sample['id']}_{idx}", sample["id"], item["name"], item.get("quantity"), item.get("unit_price"), item.get("total"), idx))
        conn.commit()
    conn.close()
    return {"status": "success", "message": "Samples loaded"}

# Mount static folder
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "samples"), exist_ok=True)

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("server:app", host=host, port=port, reload=True)
