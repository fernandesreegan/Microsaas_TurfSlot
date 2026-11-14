# CLAUDE.md - TurfSlot Project Rules

> Project-specific rules for Claude Code. This file is read automatically.

---

## Project Overview

**Project Name:** TurfSlot
**Description:** A turf-booking platform. Players search turfs and book slots with online payment; turf owners manage turfs, availability, pricing and bookings.
**Roles:** `player`, `owner`, `admin`
**Tech Stack:**
- Backend: FastAPI + Python 3.11+
- Frontend: React + Vite + TypeScript
- Database: PostgreSQL + SQLAlchemy 2.x + Alembic
- Auth: Email/Password (JWT access + refresh, bcrypt)
- UI: Tailwind CSS + shadcn/ui + Framer Motion
- Payments: Dodo Payments
- Email: SMTP

---

## Project Structure

```
turfslot/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   │   ├── user.py            # User, RefreshToken, PasswordResetToken, EmailVerificationToken
│   │   │   ├── turf.py            # Turf, TurfPricingRule
│   │   │   ├── blocked_slot.py    # BlockedSlot
│   │   │   ├── booking.py         # Booking
│   │   │   └── payment.py         # Payment, WebhookEvent
│   │   ├── schemas/
│   │   ├── routers/               # auth, turfs, slots, bookings, payments, owner, admin
│   │   ├── services/
│   │   │   ├── availability.py    # slot grid + status/price resolution
│   │   │   ├── booking.py         # hold, confirm, cancel, refund policy
│   │   │   ├── dodo.py            # Dodo Payments client + webhook verification
│   │   │   ├── email.py           # SMTP + templates
│   │   │   └── scheduler.py       # hold expiry / completion job
│   │   └── auth/
│   ├── alembic/
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/            # ui/ (shadcn), SlotPicker, BookingCard, ...
│   │   ├── pages/                 # public/, player/, owner/, admin/
│   │   ├── hooks/
│   │   ├── services/              # typed API client
│   │   ├── context/               # AuthContext
│   │   └── types/
│   └── package.json
├── .claude/
│   └── commands/
├── skills/
├── agents/
└── PRPs/
```

---

## Code Standards

### Python (Backend)
```python
# ALWAYS use type hints
def get_booking(db: Session, booking_id: int) -> Booking:
    pass

# ALWAYS add docstrings for public functions
def create_booking(db: Session, player: User, data: BookingCreate) -> Booking:
    """
    Create a pending booking with a 10-minute hold.

    Args:
        db: Database session
        player: Authenticated player making the booking
        data: Booking creation data (turf_id, start_at, slot_count)

    Returns:
        Created Booking object in `pending` status
    """
    pass

# Async endpoints
@router.get("/bookings/{id}")
async def get_booking(id: int, db: Session = Depends(get_db)) -> BookingRead:
    pass
```

### TypeScript (Frontend)
```typescript
// ALWAYS define interfaces for props and data
type SlotStatus = 'available' | 'held' | 'booked' | 'blocked' | 'past';

interface Slot {
  start_at: string; // ISO 8601 UTC
  end_at: string;
  status: SlotStatus;
  price: number;    // minor units
}

// NO any types allowed
const fetchSlots = async (turfId: number, date: string): Promise<Slot[]> => {
  // ...
};
```

---

## Forbidden Patterns

### Backend
- ❌ Never use `print()`; use the `logging` module
- ❌ Never store passwords in plain text; use bcrypt
- ❌ Never store refresh/reset/verification tokens in plain text; store a hash
- ❌ Never hardcode secrets; use environment variables
- ❌ Never use `SELECT *`; specify columns
- ❌ Never skip input validation
- ❌ Never use floats for money; use integer minor units
- ❌ Never use naive datetimes; use timezone-aware UTC (`timestamptz`)
- ❌ Never confirm a booking from the payment redirect; only from a verified webhook
- ❌ Never trust prices sent by the client; recompute server-side

### Frontend
- ❌ Never use `any` type
- ❌ Never leave console.log in production
- ❌ Never skip error handling in async operations
- ❌ Never use inline styles; use Tailwind classes and shadcn/ui components
- ❌ Never format money or times ad hoc; use the shared formatters (turf timezone, currency)

---

## Module-Specific Rules

### Auth Module
- Roles: `player` | `owner` | `admin`. Registration may set only `player` or `owner`.
- Inactive users cannot log in, and their refresh tokens are rejected.
- `/auth/forgot-password` always returns 200 (no user enumeration).

### Turfs Module
- Every turf belongs to an owner (`owner_id` FK). Owners can only modify their own turfs.
- `slot_duration_minutes` must be one of: 30, 60, 90.
- `closing_time > opening_time` (no overnight hours in the MVP).
- Pricing rules on the same turf and day must not overlap. `base_price` is the fallback.
- Delete is a soft delete (`is_active=false`) and is blocked while future confirmed bookings exist.

### Slots & Availability Module
- Slots are **computed**, not stored. The grid comes from turf hours, slot length and timezone.
- Slot status values: `available` | `held` | `booked` | `blocked` | `past`.
- A pending booking counts as `held` only while `hold_expires_at > now()`.
- Blocks cannot overlap pending or confirmed bookings.
- Slots can be booked at most `BOOKING_WINDOW_DAYS` ahead.

### Bookings & Payments Module
- Booking status must be one of: `pending` | `confirmed` | `cancelled` | `completed` | `expired`.
- Allowed transitions: `pending → confirmed | cancelled | expired`, `confirmed → cancelled | completed`. Anything else is a bug.
- Double-booking is prevented by the Postgres exclusion constraint (gist over `turf_id` + `tstzrange(start_at, end_at)` for pending/confirmed). Handle `IntegrityError` and return **409**.
- Before inserting a booking, expire stale holds for that turf in the same transaction.
- Hold length: `BOOKING_HOLD_MINUTES` (10). Max consecutive slots: `MAX_SLOTS_PER_BOOKING` (4).
- Players cannot book their own turf.
- Refund policy: a player cancelling ≥24h before `start_at` gets a full refund; under 24h gets no refund. An owner or admin cancelling always gives a full refund.
- If a payment arrives after the hold expired: confirm when the slot is still free, otherwise auto-refund.
- Webhooks: verify the signature, then dedupe by `event_id` in `WebhookEvent`, and process inside a transaction.

### Owner Dashboard Module
- All queries are scoped to `owner_id = current_user.id`.
- Occupancy = booked slot-hours ÷ open slot-hours in the range. Revenue = confirmed + completed minus refunded.

### Email Module
- Send as FastAPI background tasks. A send failure is logged and never fails the request.

### Admin Module
- All `/admin/*` routes require `role == admin`. Return 403 otherwise.

---

## API Conventions

- All endpoints prefixed with `/api/v1/`
- Use plural nouns for resources: `/turfs`, `/bookings`, `/payments`
- Owner-scoped collections live under `/owner/...`; admin under `/admin/...`
- Return appropriate HTTP status codes:
  - 200: Success
  - 201: Created
  - 400: Bad Request
  - 401: Unauthorized
  - 403: Forbidden (wrong role / not owner)
  - 404: Not Found
  - 409: Conflict (slot already taken, overlapping rule/block)
  - 422: Validation error
- Datetimes are ISO 8601 UTC in API payloads. Dates for slot queries are turf-local `YYYY-MM-DD`.
- Paginated responses: `{ items, total, page, page_size }`

---

## Authentication

Email/password only. No OAuth in the MVP.

### JWT Configuration
- Access token expires: 30 minutes
- Refresh token expires: 7 days (rotated on every refresh, old one revoked)
- Algorithm: HS256
- Password reset token expires: 1 hour; email verification token: 24 hours

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/turfslot

# Auth
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Booking rules
BOOKING_HOLD_MINUTES=10
MAX_SLOTS_PER_BOOKING=4
BOOKING_WINDOW_DAYS=30
FREE_CANCELLATION_HOURS=24
DEFAULT_CURRENCY=INR
SCHEDULER_ENABLED=true

# Dodo Payments
DODO_PAYMENTS_API_KEY=your-dodo-api-key
DODO_PAYMENTS_WEBHOOK_SECRET=your-dodo-webhook-secret
DODO_PAYMENTS_ENVIRONMENT=test_mode
DODO_BOOKING_PRODUCT_ID=your-pay-what-you-want-product-id

# Email (SMTP)
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=TurfSlot <no-reply@turfslot.local>

# URLs
FRONTEND_URL=http://localhost:5173

# Frontend
VITE_API_URL=http://localhost:8000
```

---

## Development Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Docker
docker-compose up -d

# Tests
pytest backend/tests -v
cd frontend && npm test

# Linting
ruff check backend/
cd frontend && npm run lint && npm run type-check
```

---

## Validation

```bash
ruff check backend/ && pytest
npm run lint && npm run type-check
docker-compose build
```

---

## Commit Message Format

```
feat([module]): add [feature]
fix([module]): fix [bug]
refactor([module]): refactor [component]
test([module]): add tests for [feature]
docs: update [documentation]
```

Modules: `auth`, `turfs`, `slots`, `bookings`, `payments`, `dashboard`, `email`, `admin`, `infra`

---

## Skills Reference

| Task | Skill to Read |
|------|---------------|
| Database models | skills/DATABASE.md |
| API + Auth | skills/BACKEND.md |
| React + UI | skills/FRONTEND.md |
| Testing | skills/TESTING.md |
| Deployment | skills/DEPLOYMENT.md |

---

## Agent Coordination

For complex tasks, the ORCHESTRATOR coordinates:
- DATABASE-AGENT → Backend models
- BACKEND-AGENT → API development
- FRONTEND-AGENT → UI components
- TEST-AGENT → Testing
- REVIEW-AGENT → Code review
- DEVOPS-AGENT → Deployment

Read agent definitions in `/agents/` folder.
