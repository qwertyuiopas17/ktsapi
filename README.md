# KTS API — Karma Tattva Samīkṣā
> *"Examining the truth of every transaction."*

All-in-one distributor management backend: OCR purchase capture, live inventory,
GST billing, party ledger, and profit analytics.

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
copy .env.example .env
# Edit .env with your PostgreSQL connection string

# 4. Create the database
# Make sure PostgreSQL is running, then:
createdb kts_db              # or use pgAdmin

# 5. Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 6. Open API docs
# http://localhost:8000/docs
```

## API Endpoints

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/` | Health check |
| `POST` | `/api/v1/auth/send-otp` | Send OTP to phone |
| `POST` | `/api/v1/auth/verify-otp` | Verify OTP → JWT |
| `POST` | `/api/v1/auth/setup-business` | Complete business profile |
| `GET/POST` | `/api/v1/products` | Product CRUD |
| `GET` | `/api/v1/products/hsn-lookup` | HSN → GST rate lookup |
| `GET/POST` | `/api/v1/customers` | Customer CRUD |
| `GET/POST` | `/api/v1/companies` | Company (supplier) CRUD |

## Project Structure

```
kts-api/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py             # Settings from .env
│   ├── database.py           # SQLAlchemy engine + session
│   ├── models/
│   │   └── models.py         # All 15 database tables
│   ├── schemas/
│   │   ├── auth.py           # Auth request/response DTOs
│   │   └── entities.py       # Product, Customer, Company DTOs
│   ├── routers/
│   │   ├── auth.py           # OTP + JWT endpoints
│   │   ├── products.py       # Product CRUD
│   │   └── parties.py        # Customer + Company CRUD
│   ├── services/
│   │   ├── gst_engine.py     # GST calculation engine
│   │   ├── inventory_service.py  # Stock mutations + audit trail
│   │   └── ocr/              # OCR pipeline (Sprint 4-5)
│   └── utils/
│       └── unit_converter.py # Bag ↔ Kg conversions
├── alembic/                  # Database migrations
├── requirements.txt
└── .env.example
```

## Tech Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL + SQLAlchemy 2.0
- **Auth**: Firebase Phone Auth + JWT
- **OCR**: Google Document AI + PyMuPDF (coming Sprint 4)
- **Storage**: AWS S3 (bill images)
