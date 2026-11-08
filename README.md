# Court Booking Service - Backend

Production-ready backend service for managing sports court availability, temporary holds, confirmed bookings, cancellation rules, and weekly utilization reporting.

---

## 🛠 Technology Stack

- **Runtime & Language:** Python 3.11+
- **Web Framework:** FastAPI
- **ORM & Migrations:** SQLAlchemy 2.0, Alembic
- **Database:** PostgreSQL 15 (asyncpg driver)
- **Containerization:** Docker & Docker Compose
- **Testing:** Pytest, pytest-asyncio, HTTPX
- **Linter & Formatter:** Ruff
- **Type Checker:** Mypy (strict mode)

---

## 📁 Clean Architecture Directory Structure

```text
court-booking-service/
├── app/
│   ├── api/             # HTTP endpoints and routing
│   │   └── v1/
│   │       └── router.py
│   ├── core/            # Configuration, logging, security, database session
│   │   └── config.py
│   ├── models/          # SQLAlchemy ORM models (Persistence layer)
│   ├── repositories/    # Data access layer (Queries, DB operations)
│   ├── schemas/         # Pydantic schemas / DTOs (Validation & serialization)
│   ├── services/        # Domain business logic (Holds, Bookings, Pricing)
│   └── main.py          # Application entrypoint & factory
├── tests/               # Unit, integration, and concurrency tests
│   ├── conftest.py
│   └── test_health.py
├── .dockerignore        # Exclusions for Docker build context
├── .env.example         # Example environment variables template
├── .gitignore           # Git ignore rules
├── Dockerfile           # Multi-stage production container image
├── docker-compose.yml   # PostgreSQL container orchestration
├── pyproject.toml       # Modern Python packaging & tool configurations
├── requirements.txt     # Production dependencies
├── requirements-dev.txt # Development & test dependencies
└── README.md
```

---

## 🚀 Getting Started (Phase 0 Setup)

### 1. Prerequisites
- Python 3.11+
- Docker & Docker Compose (for PostgreSQL 15)
- Git

### 2. Virtual Environment Setup

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 5. Start PostgreSQL Database
```bash
docker compose up -d db
```

### 6. Run the Application
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API Documentation will be accessible at:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🧪 Quality Assurance & Tooling

### Run Linter & Formatter (Ruff)
```bash
ruff check .
ruff format --check .
```

### Run Type Checking (Mypy)
```bash
mypy app tests
```

### Run Test Suite (Pytest)
```bash
pytest -v
```

---

## 🗺 Implementation Phases
- [x] **Phase 0:** Project setup, folder structure, dependencies, Docker, Git, and README
- [ ] **Phase 1:** Architecture Design (DESIGN.md, ER Diagram, API design, assumptions)
- [ ] **Phase 2:** Database Design (SQLAlchemy models, relationships, indexes, constraints)
- [ ] **Phase 3:** Database Configuration (Session management, Alembic, connection pool)
- [ ] **Phase 4:** Authentication Placeholder (Member & Staff roles)
- [ ] **Phase 5:** Court Management (Venue, Court, Availability)
- [ ] **Phase 6:** Booking Hold System (Hold expiration, concurrency protection)
- [ ] **Phase 7:** Booking Confirmation (Idempotency, transactions)
- [ ] **Phase 8:** Booking Cancellation (Refund rules, 24h cancellation)
- [ ] **Phase 9:** Recurring Bookings (Weekly recurring bookings, conflict detection)
- [ ] **Phase 10:** Availability API (Dynamic slot computation)
- [ ] **Phase 11:** Pricing Engine (Peak & off-peak pricing)
- [ ] **Phase 12:** Booking Limits (Maximum 3 active bookings per user)
- [ ] **Phase 13:** Reports (Weekly court utilization report)
- [ ] **Phase 14:** Testing (Unit, integration, and concurrency tests)
- [ ] **Phase 15:** Docker (Full stack multi-container orchestration)
- [ ] **Phase 16:** CI/CD (GitHub Actions workflow)
- [ ] **Phase 17:** Documentation (API guides, LIMITATIONS.md)
- [ ] **Phase 18:** Final Review & Code Cleanup

