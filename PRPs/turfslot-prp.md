# PRP: TurfSlot

> Implementation blueprint for parallel agent execution

---

## METADATA

| Field | Value |
|-------|-------|
| **Product** | TurfSlot |
| **Type** | SaaS: two-sided booking marketplace |
| **Version** | 1.0 |
| **Created** | 2026-11-14 |
| **Complexity** | High (concurrency-safe booking, payments + webhooks, timezone-aware slot engine, 3 roles) |
| **Source** | INITIAL.md, CLAUDE.md |

---

## PRODUCT OVERVIEW

**Description:** Players search sports turfs by city, sport and date, see live slot availability, book consecutive slots and pay online with Dodo Payments. Turf owners list turfs and set hours, slot length and peak pricing. They block slots, manage bookings and track occupancy and revenue. Admins moderate users and turfs.

**Value Proposition:**
- *Owners*: replace phone/WhatsApp booking chaos with an always-on booking page. They get prepaid bookings, no double-bookings, automatic refunds and visibility into revenue.
- *Players*: see real availability and book and pay in under a minute, with a clear 24h free-cancellation policy.

**MVP Scope:**
- [ ] Email/password auth with player/owner roles, email verification, password reset
- [ ] Turf listing (owner CRUD + pricing rules) and public search/detail
- [ ] Computed slot availability, owner slot blocking
- [ ] Booking with 10-min hold, DB-enforced no double-booking, cancellation with 24h refund policy
- [ ] Dodo Payments checkout, webhook confirmation, refunds
- [ ] Owner dashboard (bookings, occupancy, revenue) + transactional emails
- [ ] Admin panel (users, turfs, bookings, stats)

---

## TECH STACK

| Layer | Technology | Skill Reference |
|-------|------------|-----------------|
| Backend | FastAPI + Python 3.11+, Pydantic v2, pydantic-settings | skills/BACKEND.md |
| Frontend | React 18 + TypeScript (strict) + Vite, React Router, TanStack Query, react-hook-form + zod, date-fns + date-fns-tz | skills/FRONTEND.md |
| Database | PostgreSQL 16 + SQLAlchemy 2.x (sync `Session`, per skill) + Alembic, `btree_gist` extension | skills/DATABASE.md |
| Auth | JWT (python-jose, HS256) + bcrypt (passlib), hashed refresh/reset/verify tokens | skills/BACKEND.md |
| UI | Tailwind CSS + shadcn/ui + Framer Motion, lucide-react icons, Recharts (revenue chart) | skills/FRONTEND.md |
| Payments | Dodo Payments (`dodopayments` Python SDK) + Standard Webhooks signature verification | (see Payments section) |
| Email | SMTP via `aiosmtplib` + Jinja2 templates; Mailpit in dev | skills/BACKEND.md |
| Jobs | APScheduler (in-process, 1-min interval) | skills/BACKEND.md |
| Rate limiting | slowapi | skills/BACKEND.md |
| Testing | pytest + pytest-cov + httpx TestClient against **real Postgres**; Vitest + React Testing Library + MSW | skills/TESTING.md |
| Deployment | Docker + docker-compose (api, web, db, mailpit) + GitHub Actions | skills/DEPLOYMENT.md |

> **Tests must run on PostgreSQL, not SQLite.** The exclusion constraint, `tstzrange` and arrays are Postgres-only.

---

## DATABASE MODELS

All tables use `id: int PK`. `created_at`/`updated_at` come from `TimestampMixin` (timestamptz). Money is `Integer` in minor units, and all datetimes are `DateTime(timezone=True)` in UTC. Use SQLAlchemy `Enum` types for the enums below (native PG enums).

### Enums
```
UserRole:        player | owner | admin
SportType:       football | cricket | badminton | tennis | basketball | pickleball | other
BookingStatus:   pending | confirmed | cancelled | completed | expired
CancelledBy:     player | owner | admin | system
RefundStatus:    none | pending | refunded | failed
PaymentStatus:   pending | succeeded | failed | refunded | refund_failed
```

### User (`users`)
- id, email (unique, stored lowercased, indexed), hashed_password, full_name, phone (nullable), role (UserRole, default player), is_active (default true), is_verified (default false), created_at, updated_at
- Relationships: turfs (owner), bookings (player), refresh_tokens

### RefreshToken (`refresh_tokens`)
- id, user_id (FK users, cascade), token_hash (unique, sha256), expires_at, revoked (bool), created_at

### PasswordResetToken (`password_reset_tokens`)
- id, user_id (FK), token_hash (unique), expires_at (1h), used_at (nullable), created_at

### EmailVerificationToken (`email_verification_tokens`)
- id, user_id (FK), token_hash (unique), expires_at (24h), used_at (nullable), created_at

### Turf (`turfs`)
- id, owner_id (FK users, indexed), name, slug (unique), description, address, city (indexed, stored normalized lowercase plus `city_display`), latitude/longitude (Numeric, nullable), timezone (str, IANA, validated with `zoneinfo`), sport_types (ARRAY(SportType), GIN index), amenities (ARRAY(String)), image_urls (ARRAY(String)), slot_duration_minutes (int, CHECK IN (30,60,90)), opening_time (Time), closing_time (Time, CHECK closing_time > opening_time), base_price (int ≥ 0), currency (char(3)), is_active (default true), created_at, updated_at
- Relationships: owner, pricing_rules, blocked_slots, bookings

### TurfPricingRule (`turf_pricing_rules`)
- id, turf_id (FK cascade), day_of_week (smallint 0=Mon…6=Sun, nullable = every day), start_time, end_time (CHECK end > start), price (int ≥ 0), label, created_at
- Overlap validation is done in the service layer: rules overlap if their days intersect (null counts as all days) and their time ranges intersect.
- Price resolution for a slot: the rule with a specific `day_of_week` wins over a null-day rule. Within the same specificity, the rule containing the slot's local start time applies. Otherwise `base_price` applies.

### BlockedSlot (`blocked_slots`)
- id, turf_id (FK cascade, indexed), start_at, end_at (CHECK end > start), reason (nullable), created_by (FK users), created_at
- Constraint: `EXCLUDE USING gist (turf_id WITH =, tstzrange(start_at, end_at) WITH &&)` (no overlapping blocks)

### Booking (`bookings`)
- id, booking_ref (unique, 8-char uppercase alphanumeric, e.g. `TS7K2M9Q`), player_id (FK users, indexed), turf_id (FK turfs, indexed), start_at, end_at, slot_count (int 1..MAX), total_amount (int), currency, status (BookingStatus, indexed), hold_expires_at (nullable), cancelled_by (nullable), cancelled_at (nullable), cancellation_reason (nullable), refund_status (default none), created_at, updated_at
- **Constraint (critical):**
  ```sql
  CREATE EXTENSION IF NOT EXISTS btree_gist;
  ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap
    EXCLUDE USING gist (turf_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&)
    WHERE (status IN ('pending', 'confirmed'));
  ```
- Index: `(turf_id, start_at)`, `(status, hold_expires_at)`
- Relationships: player, turf, payments

### Payment (`payments`)
- id, booking_id (FK, indexed), provider (str, `dodo`), provider_payment_id (unique, nullable until known), checkout_session_id (nullable), amount, currency, status (PaymentStatus), provider_refund_id (nullable), created_at, updated_at

### WebhookEvent (`webhook_events`)
- id, provider, event_id (unique), event_type, payload (JSONB), processed_at (nullable), created_at

**Total: 10 models.** Use a single initial Alembic migration plus `btree_gist`. The migration must contain the raw `EXCLUDE` constraints because autogenerate will not detect them.

---

## SHARED API CONTRACT

> Backend and frontend build against this contract in parallel. Backend Pydantic schema names are the source of truth, and frontend `types/` mirror them exactly.

- Base URL: `${VITE_API_URL}/api/v1`
- Auth header: `Authorization: Bearer <access_token>`
- Error shape: `{ "detail": string, "code"?: string }`. Machine codes: `SLOT_UNAVAILABLE`, `HOLD_EXPIRED`, `NOT_OWNER`, `EMAIL_TAKEN`, `INVALID_CREDENTIALS`, `EMAIL_NOT_VERIFIED`, `OVERLAPPING_RULE`, `OVERLAPPING_BLOCK`, `BOOKING_CONFLICT_WITH_BLOCK`, `INVALID_TRANSITION`, `OUTSIDE_BOOKING_WINDOW`, `OWN_TURF`
- Pagination: `Page[T] = { items: T[], total: number, page: number, page_size: number }` (defaults page=1, page_size=20, max 100)
- Datetimes are ISO 8601 with `Z`. `date` query params are turf-local `YYYY-MM-DD`. Times (`opening_time`) are `HH:MM`.

### Key schemas
```ts
type UserRole = 'player' | 'owner' | 'admin';
interface UserRead { id: number; email: string; full_name: string; phone: string | null; role: UserRole; is_active: boolean; is_verified: boolean; created_at: string; }
interface TokenPair { access_token: string; refresh_token: string; token_type: 'bearer'; }
interface RegisterRequest { email: string; password: string; full_name: string; phone?: string; role: 'player' | 'owner'; } // password: min 8, 1 letter + 1 digit

type SportType = 'football' | 'cricket' | 'badminton' | 'tennis' | 'basketball' | 'pickleball' | 'other';
interface TurfRead { id: number; slug: string; name: string; description: string; address: string; city: string; latitude: number | null; longitude: number | null; timezone: string; sport_types: SportType[]; amenities: string[]; image_urls: string[]; slot_duration_minutes: 30 | 60 | 90; opening_time: string; closing_time: string; base_price: number; currency: string; is_active: boolean; owner_id: number; }
interface TurfCreate { /* TurfRead minus id/slug/is_active/owner_id */ }
interface PricingRuleRead { id: number; day_of_week: number | null; start_time: string; end_time: string; price: number; label: string; }

type SlotStatus = 'available' | 'held' | 'booked' | 'blocked' | 'past';
interface SlotRead { start_at: string; end_at: string; status: SlotStatus; price: number; }
interface DaySlots { turf_id: number; date: string; timezone: string; currency: string; slots: SlotRead[]; }
interface BlockedSlotCreate { start_at: string; end_at: string; reason?: string; }

type BookingStatus = 'pending' | 'confirmed' | 'cancelled' | 'completed' | 'expired';
type RefundStatus = 'none' | 'pending' | 'refunded' | 'failed';
interface BookingCreate { turf_id: number; start_at: string; slot_count: number; }
interface BookingRead { id: number; booking_ref: string; turf: { id: number; name: string; slug: string; city: string; timezone: string }; player: { id: number; full_name: string; email: string }; start_at: string; end_at: string; slot_count: number; total_amount: number; currency: string; status: BookingStatus; hold_expires_at: string | null; cancelled_by: string | null; cancelled_at: string | null; cancellation_reason: string | null; refund_status: RefundStatus; refund_eligible: boolean; created_at: string; }
interface BookingCheckout { booking: BookingRead; checkout_url: string; }
interface CancelRequest { reason?: string; }

interface OwnerSummary { bookings_today: number; upcoming_bookings: BookingRead[]; occupancy_pct: number; revenue: number; refunds: number; cancellations: number; currency: string; }
interface RevenuePoint { period_start: string; revenue: number; bookings: number; }
interface AdminStats { users_by_role: Record<UserRole, number>; turfs_active: number; bookings_by_status: Record<BookingStatus, number>; gmv: number; refunds: number; }
```

---

## MODULES

### Module 1: Authentication
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /auth/register | public, rate-limited 5/min | Create player/owner account and send verification email → 201 `UserRead` |
| POST | /auth/login | public, rate-limited 10/min | Email/password → `TokenPair` (403 if inactive) |
| POST | /auth/refresh | public | Rotate refresh token → `TokenPair` (old token revoked; reusing a revoked token revokes all of that user's tokens) |
| POST | /auth/logout | user | Revoke given refresh token → 204 |
| GET | /auth/me | user | Current user |
| PUT | /auth/me | user | Update full_name, phone |
| POST | /auth/change-password | user | Requires current password; revokes other refresh tokens |
| POST | /auth/forgot-password | public, rate-limited 3/min | Always 200 |
| POST | /auth/reset-password | public | `{token, new_password}` |
| POST | /auth/verify-email | public | `{token}` |
| POST | /auth/resend-verification | user, rate-limited | Resend verification |

**Rules:** Unverified users can log in and browse, but `POST /bookings` and `POST /turfs` require `is_verified` (otherwise 403 `EMAIL_NOT_VERIFIED`). Tokens sent by email are random 32-byte URL-safe strings. Only the sha256 hash is stored.

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /login | LoginPage | MeshBackground, GlassCard, LoginForm, GradientButton |
| /register | RegisterPage | RegisterForm (player/owner segmented toggle) |
| /forgot-password | ForgotPasswordPage | EmailForm |
| /reset-password | ResetPasswordPage | ResetPasswordForm (reads `?token=`) |
| /verify-email | VerifyEmailPage | Auto-submits `?token=`, success/error state |
| /profile | ProfilePage (protected) | ProfileForm, ChangePasswordForm, VerificationBanner |

---

### Module 2: Turfs
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /turfs | public | Search: `city`, `sport`, `q` (name ILIKE), `date` (only turfs with ≥1 available slot that date, best-effort), paging → `Page[TurfRead]` |
| GET | /turfs/{id_or_slug} | public | Detail + pricing rules |
| POST | /turfs | owner, verified | Create → 201 (slug from name; add `-2`, `-3`… on collision) |
| PUT | /turfs/{id} | owner (own) | Update |
| DELETE | /turfs/{id} | owner (own) | Soft-deactivate; 409 if future confirmed bookings exist |
| GET | /owner/turfs | owner | Own turfs, including inactive |
| GET | /turfs/{id}/pricing-rules | public | List |
| POST | /turfs/{id}/pricing-rules | owner (own) | Create; 409 `OVERLAPPING_RULE` |
| PUT | /turfs/{id}/pricing-rules/{rule_id} | owner (own) | Update; 409 on overlap |
| DELETE | /turfs/{id}/pricing-rules/{rule_id} | owner (own) | 204 |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| / | HomePage | Hero, SearchBar (city, sport select, date picker), FeaturedTurfs |
| /turfs | TurfSearchPage | FilterBar, TurfCard grid, Pagination, EmptyState |
| /turfs/:slug | TurfDetailPage | ImageGallery, AmenityBadges, PriceInfo, **SlotPicker** |
| /owner/turfs | OwnerTurfsPage | TurfTable (status, actions) |
| /owner/turfs/new | TurfFormPage | TurfForm (hours, slot length, timezone select, sports multi-select, image URL list) |
| /owner/turfs/:id/edit | TurfFormPage | TurfForm + PricingRulesEditor |

---

### Module 3: Slots & Availability
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Availability algorithm** (`services/availability.py`, pure functions plus one query per input set):
```
get_day_slots(turf, local_date, now):
  tz = ZoneInfo(turf.timezone)
  grid = [ (local_date + opening_time + k*dur) … while slot_end <= closing_time ] → convert to UTC
  day_start_utc, day_end_utc = grid bounds
  bookings  = SELECT start_at, end_at, status, hold_expires_at FROM bookings
              WHERE turf_id=… AND status IN ('pending','confirmed')
              AND tstzrange(start_at,end_at) && tstzrange(day_start_utc, day_end_utc)
  blocks    = SELECT start_at, end_at FROM blocked_slots WHERE … overlap …
  rules     = turf.pricing_rules
  for slot in grid:
     status = past     if slot.start_at <= now
            | blocked  if overlaps any block
            | booked   if overlaps confirmed booking
            | held     if overlaps pending booking with hold_expires_at > now
            | available
     price  = resolve_price(rules, local weekday, local start time) or base_price
```
- Handle DST using `zoneinfo`. Build local datetimes and then convert, and add tests for one DST-observing timezone (e.g. `Europe/London`).
- `date` outside `[today, today + BOOKING_WINDOW_DAYS]` → 400 `OUTSIDE_BOOKING_WINDOW` (past dates allowed for owners only).

**Backend Endpoints:**
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /turfs/{id}/slots?date= | public | `DaySlots` |
| GET | /turfs/{id}/blocked-slots?from=&to= | owner (own) | List blocks |
| POST | /turfs/{id}/blocked-slots | owner (own) | Accepts `BlockedSlotCreate[]` (multiple slots); must be grid-aligned; 409 `BOOKING_CONFLICT_WITH_BLOCK` if it overlaps a pending/confirmed booking, 409 `OVERLAPPING_BLOCK` |
| DELETE | /turfs/{id}/blocked-slots/{block_id} | owner (own) | 204 |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| (on /turfs/:slug) | SlotPicker | DateStrip (next N days), SlotGrid (status-colored, animated), selection limited to consecutive available slots ≤ MAX, PriceSummary, "Book now" → POST /bookings |
| /owner/turfs/:id/calendar | OwnerCalendarPage | TurfSelect, DayView/WeekView grid with bookings/holds/blocks, BlockSlotDialog, UnblockAction |

---

### Module 4: Bookings & Payments
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Create booking transaction** (`services/booking.py`):
```
create_booking(db, player, data):
  validate: player verified; turf active; player != turf.owner (OWN_TURF);
            1 <= slot_count <= MAX; start_at grid-aligned; within window; not past;
            all slots inside opening hours; no block overlap
  total = sum(resolve_price(slot) for each slot)          # server-side
  BEGIN
    UPDATE bookings SET status='expired'
      WHERE turf_id=:t AND status='pending' AND hold_expires_at < now()
    INSERT booking(status='pending', hold_expires_at=now()+HOLD, ...)
  COMMIT  → on IntegrityError (exclusion violation, SQLSTATE 23P01) → 409 SLOT_UNAVAILABLE
  create Dodo checkout (outside the DB txn) → INSERT payment(status='pending', checkout_session_id)
  return BookingCheckout
```

**State machine** (in `services/booking.py`; any other transition raises `INVALID_TRANSITION`):
```
pending   → confirmed (webhook) | cancelled (player/owner/admin) | expired (system)
confirmed → cancelled (player/owner/admin) | completed (system, after end_at)
```

**Cancellation and refunds:**
| Who | When | Result |
|-----|------|--------|
| Player | pending | cancelled, hold released, no refund |
| Player | confirmed, `start_at - now >= FREE_CANCELLATION_HOURS` | cancelled, full refund (`refund_status=pending` → webhook → `refunded`) |
| Player | confirmed, `< FREE_CANCELLATION_HOURS` | cancelled, `refund_status=none` (UI warns first; `refund_eligible` in BookingRead drives the warning) |
| Owner/Admin | pending or confirmed (future) | cancelled, full refund if paid, player emailed |

**Scheduler job** (`services/scheduler.py`, every 60s, started in FastAPI lifespan, disabled when `SCHEDULER_ENABLED=false` in tests):
- `pending` with `hold_expires_at < now()` → `expired`
- `confirmed` with `end_at < now()` → `completed`

**Backend Endpoints:**
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /bookings | player/owner, verified | Create pending + checkout → 201 `BookingCheckout`; 409 `SLOT_UNAVAILABLE` |
| POST | /bookings/{id}/checkout | booking's player | New checkout URL if still pending and hold valid; else 409 `HOLD_EXPIRED` |
| GET | /bookings/me | user | `scope=upcoming\|past`, `status`, paging → `Page[BookingRead]` |
| GET | /bookings/{id} | player / turf owner / admin | `BookingRead` |
| POST | /bookings/{id}/cancel | player / turf owner / admin | Applies policy → `BookingRead` |
| GET | /owner/bookings | owner | `turf_id`, `date`, `status`, paging |
| POST | /payments/webhooks/dodo | signature | See below |

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /checkout/:bookingId | CheckoutPage | BookingSummary, HoldCountdown (from `hold_expires_at`), "Pay" → redirect to `checkout_url`; expired state with "Pick another slot" |
| /bookings/:id | BookingDetailPage | StatusBadge, polls `GET /bookings/{id}` every 2s (max 60s) while `pending`, success animation on `confirmed`, CancelBookingDialog |
| /my-bookings | MyBookingsPage | Tabs (Upcoming / Past), BookingCard list, CancelBookingDialog (refund warning) |
| /owner/bookings | OwnerBookingsPage | Filters (turf, date, status), BookingsTable, owner CancelBookingDialog |

---

### Payments: Dodo Payments integration (`services/dodo.py`)

> ⚠️ **Verify SDK method names and payload fields against the current Dodo Payments docs before implementing.** Keep all Dodo-specific code behind a `PaymentGateway` protocol so that tests use a `FakePaymentGateway`.

```python
class PaymentGateway(Protocol):
    def create_checkout(self, booking: Booking, customer: User) -> CheckoutResult: ...   # → (checkout_session_id, checkout_url)
    def refund(self, payment: Payment, reason: str) -> RefundResult: ...                 # → provider_refund_id
    def verify_webhook(self, body: bytes, headers: Mapping[str, str]) -> dict: ...       # raises InvalidSignature
```
- **Dynamic price:** use one Dodo product configured as "pay what you want" (`DODO_BOOKING_PRODUCT_ID`) and pass the booking's `total_amount` as the amount for that cart line. Attach `metadata={"booking_id": str(id), "booking_ref": ref}`. Set the return URL to `${FRONTEND_URL}/bookings/{id}`.
- **Webhook verification:** Dodo uses the Standard Webhooks spec (`webhook-id`, `webhook-timestamp`, `webhook-signature` headers). Verify with `DODO_PAYMENTS_WEBHOOK_SECRET` using the `standardwebhooks` package. Reject timestamps older than 5 min.
- **Webhook handler** (`POST /payments/webhooks/dodo`):
  1. Read the raw body and verify the signature, returning 401 on failure.
  2. `INSERT webhook_events (event_id=webhook-id …) ON CONFLICT DO NOTHING`. If nothing was inserted, return 200 (duplicate).
  3. Dispatch on event type:
     - `payment.succeeded` → set `payment.status=succeeded` and the provider ids. If the booking is `pending`, mark it `confirmed` and email player + owner. If the booking is `expired` or `cancelled`, try to re-confirm: switch it to `confirmed` only if no overlap exists (exclusion constraint). Otherwise **auto-refund** and email the player.
     - `payment.failed` → `payment.status=failed` (booking stays pending until the hold expires so the player can retry)
     - `refund.succeeded` → `payment.status=refunded`, `booking.refund_status=refunded`, email player
     - `refund.failed` → `payment.status=refund_failed`, `booking.refund_status=failed`, log at ERROR
  4. Set `processed_at` and return 200. Unknown events are logged and return 200.

---

### Module 5: Owner Dashboard
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /owner/dashboard/summary?from=&to=&turf_id= | owner | `OwnerSummary` (default range: today in turf tz) |
| GET | /owner/dashboard/revenue?from=&to=&group_by=day\|week | owner | `RevenuePoint[]` |

- Occupancy % = Σ booked minutes (confirmed + completed) ÷ Σ open minutes (opening hours × days − blocked minutes) × 100, rounded to 1 decimal.
- Revenue = Σ `total_amount` of confirmed + completed bookings − Σ refunded amounts in the range. Use aggregate SQL (no N+1).

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /owner/dashboard | OwnerDashboardPage | DateRangePicker, TurfSelect, StatCard ×4 (bookings today, occupancy, revenue, cancellations), RevenueChart (Recharts), UpcomingBookingsList |
| /settings | SettingsPage | Account info, notification note, link to profile |

---

### Module 6: Email Notifications
**Agents:** BACKEND-AGENT

`services/email.py`: `send_email(to, template, context)` runs as a FastAPI `BackgroundTasks` task (or from the webhook/scheduler directly) over `aiosmtplib`. Templates are Jinja2 HTML + text in `backend/app/templates/email/`. Any exception is logged with `logger.exception` and swallowed.

| Template | Trigger | To |
|----------|---------|----|
| verify_email | register, resend | user |
| password_reset | forgot-password | user |
| booking_confirmed | payment.succeeded | player + owner |
| booking_cancelled | cancel (any actor) | player + owner |
| refund_processed | refund.succeeded | player |
| refund_failed | refund.failed | player (+ log) |
| late_payment_refunded | auto-refund | player |

All emails show times in the **turf's timezone** and amounts formatted with currency.

---

### Module 7: Admin Panel
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /admin/users | admin | `role`, `q`, `is_active`, paging |
| PUT | /admin/users/{id} | admin | `{is_active?, role?}`. Deactivating revokes refresh tokens. Admins cannot deactivate or demote themselves |
| GET | /admin/turfs | admin | All turfs, filters |
| PUT | /admin/turfs/{id} | admin | `{is_active}` |
| GET | /admin/bookings | admin | All bookings, filters |
| GET | /admin/stats | admin | `AdminStats` |

Seed the first admin with the `python -m app.scripts.create_admin --email … --password …` CLI script. There is no API path to self-promote.

**Frontend Pages:**
| Route | Page | Components |
|-------|------|------------|
| /admin | AdminDashboardPage | StatCards |
| /admin/users | AdminUsersPage | UsersTable, role/status actions |
| /admin/turfs | AdminTurfsPage | TurfsTable, activate/deactivate |
| /admin/bookings | AdminBookingsPage | BookingsTable, filters, cancel action |

---

### Infrastructure
- `GET /health` → `{status: "ok", db: "ok"}`
- Frontend route guards: `ProtectedRoute` (logged in), `RoleRoute roles={['owner']}` / `['admin']`
- Navigation by role: player (Search, My Bookings), owner (Dashboard, Turfs, Calendar, Bookings, plus everything players get), admin (Admin)
- Shared frontend utilities in `src/lib/`: `cn`, `formatMoney(minor, currency)`, `formatInTurfTz(iso, tz, pattern)`
- shadcn/ui primitives in `components/ui/`. The skill's design components (GlassCard, GradientButton, AnimatedInput, PageWrapper, MeshBackground, AnimatedList) are built on top of shadcn + Tailwind + Framer Motion

---

## PHASE EXECUTION PLAN

**Phase 1: Foundation (4 agents in parallel)**
- **DATABASE-AGENT:** `database.py`, `models/base.py` (mixins), all 10 models + enums, `models/__init__.py` exports, Alembic setup, initial migration with `btree_gist` and both `EXCLUDE` constraints, CHECK constraints and indexes
- **BACKEND-AGENT:** `main.py` (lifespan, CORS to `FRONTEND_URL`, `/api/v1` router mounting, `/health`, exception handlers with `code`), `config.py` (all env vars in CLAUDE.md), logging setup, `exceptions.py`, `auth/` (jwt, password hashing, `get_current_user`, `require_role`, `require_verified`), slowapi limiter, `PaymentGateway` protocol + `FakePaymentGateway`, empty router stubs, `requirements.txt`
- **FRONTEND-AGENT:** Vite React-TS (strict) scaffold, Tailwind + shadcn/ui init, Framer Motion, React Router layout with role-based nav, TanStack Query client, typed axios API client with refresh interceptor, `AuthContext`, `ProtectedRoute`/`RoleRoute`, **all `types/` from the Shared API Contract**, `lib/` formatters, design components, ESLint + `type-check` script
- **DEVOPS-AGENT:** `backend/Dockerfile`, `frontend/Dockerfile` + nginx, `docker-compose.yml` (db: postgres:16, api, web, mailpit), `.env.example` (all vars), `.github/workflows/ci.yml` (Postgres service, ruff, pytest --cov, npm lint/type-check/test, docker build), `.gitignore`, `.dockerignore`

**Validation Gate 1:** `pip install -r backend/requirements.txt`, `alembic upgrade head` (on a fresh DB), `npm install`, `npm run type-check`, `docker-compose config`

**Phase 2: Modules (backend + frontend in parallel per module, built against the Shared API Contract)**
| Order | Module | Backend | Frontend |
|-------|--------|---------|----------|
| 2a | Auth | auth router/service, token rotation, email tokens, `create_admin` script | Login, Register, Forgot/Reset, Verify, Profile |
| 2b | Turfs | turfs + pricing rules routers/services, slug, search | Home, Search, Turf detail shell, Owner turfs list/form, PricingRulesEditor |
| 2c | Slots | availability service (+ DST), blocked slots router | SlotPicker, OwnerCalendarPage |
| 2d | Bookings & Payments | booking service + state machine, Dodo gateway, webhook handler, scheduler | Checkout, Booking detail (polling), My Bookings, Owner Bookings |
| 2e | Email | SMTP service, templates, wired into 2a/2d | — |
| 2f | Dashboard + Admin | owner dashboard aggregates, admin routers | Owner dashboard, Settings, Admin pages |

Dependencies: 2a → (2b, 2e) → 2c → 2d → 2f. The frontend may run ahead using MSW mocks of the contract.

**Validation Gate 2:** `ruff check backend/`, `mypy backend/app` (if configured), `npm run lint`, `npm run type-check`, the app boots with `uvicorn`, and `/docs` lists all 41 endpoints

**Phase 3: Quality (3 agents in parallel)**
- **TEST-AGENT:**
  - Backend (pytest, real Postgres, `FakePaymentGateway`, SMTP mocked): auth flows (incl. refresh-token reuse detection); turf ownership/403s; pricing overlap; **availability engine unit tests** (grid, statuses, price resolution, DST); **concurrency test** where two threads book the same slot and exactly one succeeds with 409 for the other; hold expiry; webhook signature failure, idempotent replay, late-payment confirm and auto-refund paths; cancellation policy at the 24h boundary (23:59 vs 24:00); owner dashboard math; admin guards. Target **≥80% coverage**.
  - Frontend (Vitest + RTL + MSW): LoginForm, RegisterForm, SlotPicker selection rules, HoldCountdown, CancelBookingDialog refund warning, RoleRoute guarding
- **REVIEW-AGENT:** Security audit covering authz on every owner/admin route (IDOR), webhook verification, rate limits, token hashing, no secrets in code, CORS, no `print`/`console.log`/`any`/inline styles, N+1 queries, and money/timezone correctness
- **DEVOPS-AGENT:** CI green end-to-end, `docker-compose up` smoke test, seed script (`app/scripts/seed.py`: 1 admin, 2 owners, 4 turfs, 3 players, sample bookings) for local demo

**Final Validation:** Full test suite, docker build, health checks, and a manual smoke test: register owner → create turf → register player → book → (fake/test-mode) pay → confirmed email in Mailpit → cancel → refund

---

## VALIDATION GATES

| Gate | Commands |
|------|----------|
| 1 | `alembic upgrade head`, `npm install`, `npm run type-check`, `docker-compose config` |
| 2 | `ruff check backend/`, `npm run lint`, `npm run type-check` |
| 3 | `pytest backend/tests --cov=app --cov-fail-under=80`, `cd frontend && npm test` |
| Final | `docker-compose build`, `docker-compose up -d`, `curl localhost:8000/health`, `curl localhost:5173` (or the nginx port) |

---

## ENVIRONMENT VARIABLES

```env
# Database
DATABASE_URL=postgresql://turfslot:turfslot@localhost:5432/turfslot
TEST_DATABASE_URL=postgresql://turfslot:turfslot@localhost:5432/turfslot_test

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

# Email (SMTP; Mailpit in dev)
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=TurfSlot <no-reply@turfslot.local>

# URLs
FRONTEND_URL=http://localhost:5173

# Frontend
VITE_API_URL=http://localhost:8000
VITE_MAX_SLOTS_PER_BOOKING=4
```

---

## RISKS & MITIGATIONS

| Risk | Mitigation |
|------|-----------|
| Double-booking under concurrency | DB exclusion constraint is the source of truth, plus a concurrency test |
| Expired-but-unswept holds blocking new bookings | Expire stale holds for that turf in the same transaction before the insert, plus a 1-min job |
| Webhook arrives late, twice or never | Idempotent by `event_id`; the late-payment path auto-refunds; the booking page polls; holds expire |
| Dodo API differences from this spec | All Dodo code behind `PaymentGateway`; verify against docs; tests use a fake |
| DST / timezone bugs | `zoneinfo` local → UTC conversion, DST tests, UTC storage |
| Scheduler running in multiple API replicas | MVP runs a single API replica; the job is idempotent (conditional UPDATE). Post-MVP: move to a dedicated worker |

---

## SUMMARY

| Item | Count |
|------|-------|
| Modules | 7 (Auth, Turfs, Slots, Bookings & Payments, Owner Dashboard, Email, Admin) |
| Models | 10 |
| API endpoints | 41 (40 + `/health`) |
| Frontend pages | 23 |

---

## NEXT STEP

Execute with parallel agents:
/execute-prp PRPs/turfslot-prp.md
