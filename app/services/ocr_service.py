"""
KTS — OCR Invoice Scanner Service
Extracts structured data from purchase invoice images/PDFs.

Strategy (from PRD §3.3):
  Phase 1: Groq Vision API (llama-3.2-90b-vision) — free, fast, good accuracy
  Phase 2: Google Document AI — production-grade, per-supplier template learning

Pipeline:
  1. PDF → high-DPI images (PyMuPDF fitz, ported from user's extract_biology.py)
  2. Image → Groq Vision API with structured JSON prompt
  3. Parse response → PurchaseCreate schema
  4. User reviews + edits → confirm → stock_in
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path

# PDF to image conversion (ported from user's sih2026/extract_biology.py pattern)
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
    print("[KTS OCR] WARNING: PyMuPDF not installed. Run: pip install PyMuPDF", file=sys.stderr)

try:
    from groq import Groq
except ImportError:
    Groq = None
    print("[KTS OCR] WARNING: groq not installed. Run: pip install groq", file=sys.stderr)

try:
    from PIL import Image
except ImportError:
    Image = None


# ─── Groq Vision Client (with key rotation from Aethel pattern) ───
class GroqVisionClient:
    """
    Rotating Groq client for Vision API.
    Ported from aethel-backend-v3's RotatingGroqClient pattern.
    """
    def __init__(self):
        keys = []
        for i in range(1, 5):
            k = os.environ.get(f"GROQ_API_KEY_{i}")
            if k:
                keys.append(k)
        if not keys:
            k = os.environ.get("GROQ_API_KEY")
            if k:
                keys.append(k)

        self.clients = [Groq(api_key=k) for k in keys] if Groq and keys else []
        self.current_idx = 0

    def _get_client(self) -> Groq | None:
        if not self.clients:
            return None
        client = self.clients[self.current_idx]
        self.current_idx = (self.current_idx + 1) % len(self.clients)
        return client


_groq_vision = GroqVisionClient()

# Vision model
VISION_MODEL = "llama-3.2-90b-vision-preview"


# ─── PDF → Images ─────────────────────────────────────────────
def pdf_to_images(pdf_bytes: bytes, dpi: int = 200) -> list[bytes]:
    """
    Convert PDF pages to high-DPI PNG images.
    Pattern from user's extract_biology.py (PyMuPDF/fitz).
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF not installed. Run: pip install PyMuPDF")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        # High DPI for OCR accuracy (user's pattern uses 300, we use 200 for speed)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        images.append(pix.tobytes("png"))

    doc.close()
    return images


def image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 string for API consumption."""
    return base64.b64encode(image_bytes).decode("utf-8")


# ─── Invoice Extraction Prompt ────────────────────────────────
INVOICE_EXTRACTION_PROMPT = """You are an expert Indian invoice/bill reader. Extract all data from this purchase invoice image.

Return ONLY a valid JSON object with this exact structure:
{
  "company_name": "supplier company name",
  "gstin": "supplier GSTIN if visible",
  "invoice_number": "invoice/bill number",
  "invoice_date": "YYYY-MM-DD format",
  "items": [
    {
      "product_name": "item description",
      "hsn_code": "HSN/SAC code if visible",
      "quantity": 10,
      "unit": "Kg or Bag or Box or Litre or Pcs",
      "rate": 100.00,
      "discount_pct": 0,
      "gst_rate": 5,
      "amount": 1000.00
    }
  ],
  "subtotal": 1000.00,
  "cgst_amount": 25.00,
  "sgst_amount": 25.00,
  "igst_amount": 0,
  "total_amount": 1050.00,
  "confidence": 0.85
}

Rules:
- All amounts in INR (Indian Rupees)
- Dates in YYYY-MM-DD format
- If a field is not visible, use null
- confidence is your estimate of extraction accuracy (0.0 to 1.0)
- For loose items (dal, oil, etc.), identify the bulk unit (Bag, Can, Tin)
- Extract ALL line items, not just the first few
- GST rate should be the percentage (0, 5, 12, 18, 28), not the amount
"""


# ─── Core OCR Function ───────────────────────────────────────
async def extract_invoice_data(
    image_bytes: bytes,
    content_type: str = "image/png",
) -> dict:
    """
    Extract structured invoice data from an image using Groq Vision API.

    Args:
        image_bytes: Raw image bytes (PNG, JPEG, or PDF page rendered as image)
        content_type: MIME type of the image

    Returns:
        dict with extracted invoice data + confidence score
    """
    client = _groq_vision._get_client()
    if client is None:
        return {
            "error": "No Groq API key configured. Set GROQ_API_KEY environment variable.",
            "confidence": 0,
            "items": [],
        }

    b64_image = image_to_base64(image_bytes)

    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": INVOICE_EXTRACTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{content_type};base64,{b64_image}",
                            },
                        },
                    ],
                }
            ],
            temperature=0.1,  # Low temp for consistent extraction
            max_tokens=4096,
        )

        raw_text = response.choices[0].message.content

        # Parse JSON from response (handle markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw_text)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Try to find raw JSON
            json_match = re.search(r'\{[\s\S]*\}', raw_text)
            json_str = json_match.group(0) if json_match else raw_text

        data = json.loads(json_str)
        data["raw_response"] = raw_text
        data["source"] = "groq_vision"
        return data

    except json.JSONDecodeError as e:
        return {
            "error": f"Failed to parse OCR response as JSON: {e}",
            "raw_response": raw_text if 'raw_text' in dir() else "",
            "confidence": 0,
            "items": [],
        }
    except Exception as e:
        return {
            "error": f"OCR extraction failed: {str(e)}",
            "confidence": 0,
            "items": [],
        }


async def scan_invoice(file_bytes: bytes, filename: str) -> dict:
    """
    Full pipeline: file (PDF or image) → structured invoice data.

    For PDFs: converts first page to image, then runs Vision API.
    For images: runs Vision API directly.
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        # PDF → image pipeline (from user's PyMuPDF pattern)
        try:
            images = pdf_to_images(file_bytes, dpi=200)
            if not images:
                return {"error": "PDF has no pages", "items": []}
            # Process first page (most invoices are single-page)
            result = await extract_invoice_data(images[0], "image/png")
            result["pages_processed"] = 1
            result["total_pages"] = len(images)
            return result
        except Exception as e:
            return {"error": f"PDF processing failed: {e}", "items": []}

    elif ext in (".jpg", ".jpeg"):
        return await extract_invoice_data(file_bytes, "image/jpeg")
    elif ext == ".png":
        return await extract_invoice_data(file_bytes, "image/png")
    elif ext == ".webp":
        return await extract_invoice_data(file_bytes, "image/webp")
    else:
        return {"error": f"Unsupported file type: {ext}", "items": []}
