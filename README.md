# Court Booking Service - Backend

Production-ready backend service for managing sports court availability, temporary holds, confirmed bookings, cancellation rules, and weekly utilization reporting.

---

## 🛠 Technology Stack

- **Runtime & Language:** Python 3.11+
- **Web Framework:** FastAPI
- **Security & Auth:** JWT (HS256), bcrypt / PBKDF2 password hashing, RBAC
- **ORM & Migrations:** SQLAlchemy 2.0 (Async), Alembic
- **Database:** PostgreSQL 15 (asyncpg driver)
- **Containerization:** Docker & Docker Compose
- **Testing:** Pytest, pytest-asyncio, HTTPX
- **Linter & Formatter:** Ruff
- **Type Checker:** Mypy (strict mode)

---

## 📁 Clean Architecture Directory Structure

```text
court-booking-service/
├── alembic/             # Alembic database migration environment
│   ├── versions/        # Migration version revisions
│   ├── env.py           # Async migration runner with Base.metadata discovery
│   └── script.py.mako   # Migration script template
├── app/
│   ├── api/             # HTTP endpoints and routing
│   │   ├── dependencies.py # Auth guards (get_current_user, require_member/staff/admin)
│   │   └── v1/
│   │       ├── router.py   # Root v1 aggregator
│   │       └── auth.py     # Authentication endpoints (register, login, refresh, me)
│   ├── core/            # Configuration, settings, and security
│   │   ├── config.py       # Pydantic Settings & environment variables
│   │   ├── exceptions.py   # Domain exceptions
│   │   └── security.py     # Password hashing & JWT token generation/verification
│   ├── db/              # Database infrastructure (SQLAlchemy 2.0 Async)
│   │   ├── base.py      # Unified metadata registry for Alembic discovery
│   │   ├── database.py  # AsyncEngine configuration, pooling & health ping
│   │   └── session.py   # async_sessionmaker and get_db FastAPI dependency
│   ├── models/          # Declarative ORM models (Domain persistence)
│   │   ├── base.py      # DeclarativeBase, UUIDPrimaryKeyMixin, TimestampMixin
│   │   ├── enums.py     # StrEnums (UserRole, SlotStatus, BookingStatus, etc.)
│   │   ├── user.py      # User account model
│   │   ├── admin.py
│   │   ├── venue.py
│   │   ├── sport.py
│   │   ├── court.py
│   │   ├── court_image.py
│   │   ├── time_slot.py
│   │   ├── booking.py
│   │   └── payment.py
│   ├── repositories/    # Data access layer (Queries, DB operations)
│   │   └── user_repository.py # User queries and creation
│   ├── schemas/         # Pydantic schemas / DTOs (Validation & serialization)
│   │   └── auth.py      # Auth DTOs (Register, Login, Refresh, UserResponse)
│   ├── services/        # Domain business logic (Holds, Bookings, Pricing)
│   │   └── auth_service.py # Authentication, hashing, and token rotation
│   └── main.py          # Application factory & lifespan connection hooks
├── tests/               # Unit, integration, and security tests
│   ├── conftest.py
│   ├── test_auth_api.py
│   ├── test_auth_service.py
│   ├── test_database_design.py
│   ├── test_database_infrastructure.py
│   ├── test_health.py
│   ├── test_models.py
│   └── test_security.py
├── .dockerignore        # Exclusions for Docker build context
├── .env.example         # Example environment variables template
├── .gitignore           # Git ignore rules
├── alembic.ini          # Alembic CLI configuration
├── DESIGN.md            # Technical architecture blueprint & ER diagram
├── Dockerfile           # Multi-stage production container image
├── docker-compose.yml   # PostgreSQL container orchestration
├── pyproject.toml       # Modern Python packaging & tool configurations
├── requirements.txt     # Production dependencies
├── requirements-dev.txt # Development & test dependencies
└── README.md
```

---

## 🔐 Authentication & Authorization (RBAC)

The service implements JSON Web Token (JWT) authentication using the `HS256` signature algorithm and secure password hashing.

### User Roles
- **`MEMBER`**: Default registered customer role. Can browse availability, place holds, confirm bookings, and manage personal reservations.
- **`STAFF`**: Venue operator role. Can manage court schedules, check-in players, and view daily slot status.
- **`ADMIN`**: Superuser role. Full administrative access, court creation, pricing configuration, and financial reporting.

### Authentication Endpoints
| Method | Endpoint | Description | Status Code |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register a new member account | `201 Created` |
| `POST` | `/api/v1/auth/login` | Authenticate credentials and receive token pair | `200 OK` |
| `POST` | `/api/v1/auth/refresh` | Rotate access and refresh tokens | `200 OK` |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user's profile | `200 OK` |

### Security Dependencies
- `get_current_user`: Extracts and validates the Bearer token, querying the database for active user status.
- `require_member`: Enforces authenticated user with at least `MEMBER` privileges.
- `require_staff`: Enforces `STAFF` or `ADMIN` privileges.
- `require_admin`: Enforces `ADMIN` privileges exclusively.

---

## ⚙️ Environment Variables

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `APP_NAME` | `Court Booking Service` | Service identifier |
| `APP_ENV` | `development` | Deployment environment |
| `DEBUG` | `True` | Debug mode toggle |
| `HOST` | `0.0.0.0` | Binding host IP |
| `PORT` | `8000` | HTTP port |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/court_booking_db` | Async connection string for primary DB |
| `TEST_DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/court_booking_test_db` | Async connection string for test suite |
| `DB_POOL_SIZE` | `10` | Base database connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Maximum bursting connections beyond pool size |
| `DB_POOL_TIMEOUT` | `30` | Seconds to wait before timing out on pool checkout |
| `DB_POOL_RECYCLE` | `1800` | Reconnect connections after 30 minutes |
| `DB_ECHO` | `False` | Log all SQL statements to stdout |
| `JWT_SECRET_KEY` | `court-booking-jwt-secret-key-32-bytes-minimum-security-token` | Secret HMAC signing key |
| `JWT_ALGORITHM` | `HS256` | JWT signature algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Short-lived access token TTL in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Long-lived refresh token TTL in days |

---

## 🚀 Getting Started

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

### 6. Database Migrations (Alembic)
```bash
alembic revision --autogenerate -m "Initial database schema"
alembic upgrade head
```

### 7. Run the Application
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Interactive API documentation:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🧪 Quality Assurance & Tooling

```bash
# Run Linter & Formatter (Ruff)
ruff check .
ruff format --check .

# Run Type Checking (Mypy)
mypy app tests

# Run Test Suite (Pytest)
pytest -v
```

---

## 🗺 Implementation Phases
- [x] **Phase 0:** Project setup, folder structure, dependencies, Docker, Git, and README
- [x] **Phase 1:** Architecture Design (`DESIGN.md`, ER Diagram, API design, assumptions)
- [x] **Phase 2:** Database Design (SQLAlchemy models, relationships, indexes, check constraints)
- [x] **Phase 3:** Database Configuration (AsyncEngine, session management, connection pool, Alembic, environment variables)
- [x] **Phase 4 (Auth):** JWT Authentication & Authorization (Register, login, refresh, me, RBAC dependencies, password hashing)
- [x] **Phase 5:** Court Management (Venue model, Court model, Availability model)
- [x] **Phase 6:** Booking Hold System (POST /holds, hold expiration, concurrency protection)
- [x] **Phase 7:** Booking Confirmation (POST /holds/{id}/confirm, idempotency, transactions)
- [x] **Phase 8:** Booking Cancellation (Refund logic, 24-hour rule)
- [ ] **Phase 9:** Recurring Bookings (Weekly recurring bookings, conflict detection)
- [ ] **Phase 10:** Availability API (GET /courts/{id}/availability)
- [ ] **Phase 11:** Pricing Engine (Peak & off-peak hours)
- [ ] **Phase 12:** Booking Limits (Maximum 3 active bookings)
- [ ] **Phase 13:** Reports (Weekly utilization report)
- [ ] **Phase 14:** Testing (Unit tests, integration tests, concurrency tests)
- [ ] **Phase 15:** Docker (Multi-container production orchestration)
- [ ] **Phase 16:** CI/CD (GitHub Actions)
- [ ] **Phase 17:** Documentation (README, LIMITATIONS.md)
- [ ] **Phase 18:** Final Review & Code Cleanup
