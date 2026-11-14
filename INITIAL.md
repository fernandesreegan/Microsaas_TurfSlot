# INITIAL.md - TurfSlot Product Definition

> Players find sports turfs and book slots online; turf owners manage availability, pricing and bookings in one place.

---

## PRODUCT

### Name
TurfSlot

### Description
TurfSlot is a turf-booking platform with two sides:

- **Players** search turfs by city, sport and date. They see live slot availability, book one or more consecutive slots, pay online through Dodo Payments and cancel within the refund policy.
- **Turf owners** list their turfs and set opening hours, slot length (30/60/90 min) and peak/off-peak pricing. They block slots for maintenance or walk-ins, manage incoming bookings and track occupancy and revenue on a dashboard.

An **admin** oversees users, turfs and platform-wide stats.

The core guarantee is **no double-booking**. A slot is held for 10 minutes during checkout. The database enforces non-overlapping bookings, and an unpaid hold is released automatically.

### Target User
- **Players**: casual and regular footballers, cricketers and other turf-sport players who want to book a slot in seconds.
- **Turf owners and managers**: small venue operators who currently take bookings over phone or WhatsApp.

### Type
- [x] SaaS (Software as a Service), as a two-sided booking marketplace

---

## TECH STACK

### Backend
- [x] FastAPI + Python 3.11+

### Frontend
- [x] React + Vite + TypeScript

### Database
- [x] PostgreSQL + SQLAlchemy 2.x + Alembic (`btree_gist` extension for booking overlap constraint)

### Authentication
- [x] Email/Password (JWT access + refresh tokens, bcrypt hashing)

### UI Framework
- [x] Tailwind CSS + shadcn/ui (+ Framer Motion for transitions)

### Payments
- [x] Dodo Payments (checkout sessions + webhooks + refunds)

### Email
- [x] SMTP (provider-agnostic, configured via env vars)

---

## ROLES

| Role | Can do |
|------|--------|
| `player` | Search turfs, book/cancel own bookings, pay, view own bookings |
| `owner` | Everything a player can, plus CRUD own turfs, pricing rules, blocked slots, view/cancel bookings on own turfs, dashboard |
| `admin` | Manage all users and turfs, view platform stats and all bookings |

A user picks `player` or `owner` at registration. Only an admin can grant `admin`.

---

## MODULES

> All endpoints are prefixed with `/api/v1`. Times are stored as UTC `timestamptz`. Each turf has an IANA `timezone` used to compute local slot grids. Money is stored as **integer minor units** (e.g. paise/cents).

### Module 1: Authentication (Required)

**Description:** Email/password registration and login, JWT sessions, email verification and password reset.

**Models:**
- User: id, email (unique, lowercased), hashed_password, full_name, phone, role (`player`|`owner`|`admin`), is_active, is_verified, created_at, updated_at
- RefreshToken: id, user_id (FK), token_hash, expires_at, revoked, created_at
- PasswordResetToken: id, user_id (FK), token_hash, expires_at, used_at, created_at
- EmailVerificationToken: id, user_id (FK), token_hash, expires_at, used_at, created_at

**API Endpoints:**
- POST /auth/register - Create account (role: player or owner) and send verification email
- POST /auth/login - Login with email/password
- POST /auth/refresh - Rotate refresh token and issue a new access token
- POST /auth/logout - Revoke refresh token
- GET /auth/me - Get current user profile
- PUT /auth/me - Update profile (full_name, phone)
- POST /auth/change-password - Change password (requires current password)
- POST /auth/forgot-password - Email a reset link (always returns 200, so it does not reveal whether an email exists)
- POST /auth/reset-password - Reset password with token
- POST /auth/verify-email - Verify email with token
- POST /auth/resend-verification - Resend verification email

**Frontend Pages:**
- /login - Login page
- /register - Registration page (player/owner toggle)
- /forgot-password - Forgot password page
- /reset-password - Reset password page (token from email link)
- /verify-email - Email verification landing
- /profile - User profile and change password (protected)

---

### Module 2: Turfs (Venues)

**Description:** Owners create and manage turfs. Players browse and search them publicly.

**Models:**
- Turf: id, owner_id (FK users), name, slug (unique), description, address, city, latitude (nullable), longitude (nullable), timezone (IANA, e.g. `Asia/Kolkata`), sport_types (array of enum: `football`|`cricket`|`badminton`|`tennis`|`basketball`|`pickleball`|`other`), amenities (array of strings), image_urls (array of URLs, external links for MVP), slot_duration_minutes (`30`|`60`|`90`), opening_time (time), closing_time (time), base_price (int, minor units, per slot), currency (ISO 4217), is_active, created_at, updated_at
- TurfPricingRule: id, turf_id (FK), day_of_week (0-6, nullable = every day), start_time, end_time, price (int, minor units, per slot), label (e.g. "Peak", "Weekend"), created_at

**Business rules:**
- `closing_time > opening_time` (no overnight hours in the MVP). The last slot must end at or before closing.
- Pricing rules on the same turf and day must not overlap. Where no rule matches, a slot uses `base_price`.
- Deleting a turf is a soft delete (`is_active=false`) and is blocked while future confirmed bookings exist.
- Changing `slot_duration_minutes` or hours affects future grids only. Existing bookings stay valid, and overlapping grid slots show as booked.

**API Endpoints:**
- GET /turfs - Public search (`city`, `sport`, `date`, `q`, `page`, `page_size`), active turfs only
- GET /turfs/{id_or_slug} - Public turf detail
- POST /turfs - Create turf (owner)
- PUT /turfs/{id} - Update own turf (owner)
- DELETE /turfs/{id} - Deactivate own turf (owner)
- GET /owner/turfs - List the current owner's turfs
- GET /turfs/{id}/pricing-rules - List pricing rules
- POST /turfs/{id}/pricing-rules - Add pricing rule (owner)
- PUT /turfs/{id}/pricing-rules/{rule_id} - Update pricing rule (owner)
- DELETE /turfs/{id}/pricing-rules/{rule_id} - Delete pricing rule (owner)

**Frontend Pages:**
- / - Landing page with search bar (city, sport, date)
- /turfs - Search results with filters
- /turfs/:slug - Turf detail (photos, amenities, map link, slot picker)
- /owner/turfs - Owner's turf list
- /owner/turfs/new - Create turf form
- /owner/turfs/:id/edit - Edit turf, hours, slot length and pricing rules

---

### Module 3: Slots & Availability

**Description:** Slots are **computed, not stored**. For a given turf and local date, the grid comes from opening hours and slot length. Each slot's status and price are resolved against bookings, active holds, blocked slots and pricing rules.

**Models:**
- BlockedSlot: id, turf_id (FK), start_at (timestamptz), end_at (timestamptz), reason, created_by (FK users), created_at

**Slot status values (computed):** `available` | `held` (pending booking with an unexpired hold) | `booked` | `blocked` | `past`

**Business rules:**
- Players can book up to `BOOKING_WINDOW_DAYS` (default 30) days ahead.
- A blocked slot cannot overlap an existing pending or confirmed booking. The owner must cancel that booking first.
- Slot boundaries must align to the turf's grid (`opening_time + n × slot_duration`).

**API Endpoints:**
- GET /turfs/{id}/slots?date=YYYY-MM-DD - Slot grid for a local date: `[{start_at, end_at, status, price}]`
- GET /turfs/{id}/blocked-slots?from=&to= - List blocks (owner)
- POST /turfs/{id}/blocked-slots - Block one or more slots (owner)
- DELETE /turfs/{id}/blocked-slots/{block_id} - Unblock (owner)

**Frontend Pages:**
- Slot picker component on /turfs/:slug (date strip, slot grid, multi-select of consecutive slots, live price total)
- /owner/turfs/:id/calendar - Owner day/week calendar showing bookings, holds and blocks, with block/unblock actions

---

### Module 4: Bookings & Payments

**Description:** Players book consecutive slots, pay through Dodo Payments and can cancel. Owners see and manage bookings on their turfs.

**Models:**
- Booking: id, booking_ref (short human-readable, unique), player_id (FK users), turf_id (FK), start_at, end_at (timestamptz), slot_count, total_amount (int, minor units), currency, status (`pending`|`confirmed`|`cancelled`|`completed`|`expired`), hold_expires_at, cancelled_by (`player`|`owner`|`admin`|`system`, nullable), cancelled_at, cancellation_reason, refund_status (`none`|`pending`|`refunded`|`failed`), created_at, updated_at
  - **Exclusion constraint:** `EXCLUDE USING gist (turf_id WITH =, tstzrange(start_at, end_at) WITH &&) WHERE (status IN ('pending','confirmed'))`
- Payment: id, booking_id (FK), provider (`dodo`), provider_payment_id, checkout_session_id, amount, currency, status (`pending`|`succeeded`|`failed`|`refunded`|`refund_failed`), provider_refund_id, created_at, updated_at
- WebhookEvent: id, provider, event_id (unique), event_type, payload (JSONB), processed_at, created_at. Used for idempotent webhook handling.

**Business rules:**
- **Hold:** `POST /bookings` creates a `pending` booking with `hold_expires_at = now + 10 min`. In the same transaction, stale pending holds for that turf are expired first so they cannot block the new insert.
- **Expiry job:** runs every minute. It sets `pending` bookings past `hold_expires_at` to `expired` and sets `confirmed` bookings past `end_at` to `completed`.
- **Confirmation:** happens only through a verified Dodo webhook (`payment.succeeded`), never through the redirect URL. Webhooks are idempotent by `event_id`.
- **Late payment:** if a payment succeeds after the hold expired, the booking is confirmed when the slot is still free. Otherwise the payment is auto-refunded and the player is emailed.
- **Max slots per booking:** `MAX_SLOTS_PER_BOOKING` (default 4), and the slots must be consecutive.
- Players cannot book slots on their own turf, slots in the past or slots outside the booking window.
- **Cancellation policy:**
  - Player cancels **≥ 24h before `start_at`**: full refund.
  - Player cancels **< 24h before**: allowed, no refund.
  - Owner or admin cancels: always a full refund, and the player is notified.
  - Pending (unpaid) booking cancelled: the hold is released and no payment is involved.
- `total_amount` is computed server-side from pricing rules at booking time. The client-sent price is never trusted.

**API Endpoints:**
- POST /bookings - Create pending booking `{turf_id, start_at, slot_count}` and return the booking plus `checkout_url`
- POST /bookings/{id}/checkout - Get a fresh checkout URL while the hold is still valid
- GET /bookings/me - Player's bookings (`scope=upcoming|past`, `status`, paging)
- GET /bookings/{id} - Booking detail (player who owns it, turf owner or admin)
- POST /bookings/{id}/cancel - Cancel (player or owner) with optional reason; applies the refund policy
- GET /owner/bookings - Bookings across the owner's turfs (`turf_id`, `date`, `status`, paging)
- POST /payments/webhooks/dodo - Dodo webhook (signature verified, idempotent, no auth)

**Frontend Pages:**
- /checkout/:bookingId - Booking summary with hold countdown that redirects to Dodo checkout
- /bookings/:id - Booking detail and status (polls until the webhook confirms; also the Dodo return URL)
- /my-bookings - Player's upcoming and past bookings with a cancel action
- /owner/bookings - Owner's bookings table with filters and a cancel action

---

### Module 5: Owner Dashboard

**Description:** Overview for turf owners.

**API Endpoints:**
- GET /owner/dashboard/summary?from=&to=&turf_id= - Today's bookings, upcoming bookings, occupancy % (booked slot-hours ÷ open slot-hours), revenue (confirmed + completed minus refunds), cancellations
- GET /owner/dashboard/revenue?from=&to=&group_by=day|week - Revenue time series

**Frontend Pages:**
- /owner/dashboard - Stat cards (today's bookings, occupancy, revenue), upcoming bookings list, revenue chart
- /settings - Account settings and preferences

---

### Module 6: Email Notifications

**Description:** Transactional emails sent over SMTP as background tasks. Failures are logged and never block the request.

**Emails:**
- Welcome + verify email
- Password reset
- Booking confirmed (player + owner)
- Booking cancelled (player + owner), including refund info
- Refund processed / failed
- Late payment auto-refunded (player)

---

### Module 7: Admin Panel

**Description:** Admin-only management interface.

**API Endpoints:**
- GET /admin/users - List users (`role`, `q`, `is_active`, paging)
- PUT /admin/users/{id} - Update user status or role
- GET /admin/turfs - List all turfs
- PUT /admin/turfs/{id} - Activate or deactivate a turf
- GET /admin/bookings - List all bookings with filters
- GET /admin/stats - Platform stats (users by role, turfs, bookings, GMV, refunds)

**Frontend Pages:**
- /admin - Admin dashboard (protected, admin only)
- /admin/users - User management
- /admin/turfs - Turf moderation
- /admin/bookings - Booking overview

---

## MVP SCOPE

### Must Have (MVP)
- [x] User registration and login (email/password, player/owner roles, verification, password reset)
- [x] Turf listing + search (owner CRUD, pricing rules, public search and detail)
- [x] Slot booking + cancel (computed availability, 10-min hold, no double-booking, 24h refund policy)
- [x] Online payment via Dodo Payments (checkout, webhook confirmation, refunds)
- [x] Owner dashboard (bookings, blocked slots, occupancy and revenue) + transactional emails
- [x] Admin panel (users, turfs, bookings, stats)

### Nice to Have (Post-MVP)
- [ ] Turf photo uploads (S3-compatible storage); MVP uses image URLs
- [ ] Google OAuth / magic link login
- [ ] Platform-wide analytics dashboard with charts and exports
- [ ] Reviews and ratings
- [ ] Map-based / near-me search
- [ ] Recurring bookings (e.g. every Tuesday 7pm)
- [ ] Split payment among teammates
- [ ] Overnight opening hours and per-day opening hours
- [ ] Owner-configurable cancellation policies
- [ ] SMS / WhatsApp notifications
- [ ] Owner payouts and platform commission

---

## ACCEPTANCE CRITERIA

### Authentication
- [ ] User can register with email/password as a player or an owner
- [ ] User can login with email/password
- [ ] Verification email is sent and the verify link marks the user verified
- [ ] Forgot/reset password flow works end-to-end
- [ ] JWT access tokens work, and refresh rotates tokens
- [ ] Protected routes redirect to login; role-restricted routes return 403
- [ ] Auth endpoints are rate limited

### Turfs
- [ ] Owner can create, edit and deactivate their own turfs (not others')
- [ ] Owner can add pricing rules, and overlapping rules are rejected
- [ ] Public search filters by city, sport and text and only returns active turfs

### Slots & Availability
- [ ] Slot grid respects opening hours, slot length and turf timezone
- [ ] Each slot shows the correct status (available/held/booked/blocked/past) and price
- [ ] Owner can block/unblock slots; blocking a booked slot is rejected

### Bookings & Payments
- [ ] Player can book 1 to `MAX_SLOTS_PER_BOOKING` consecutive available slots
- [ ] Two concurrent requests for the same slot result in exactly one booking (DB constraint tested)
- [ ] Unpaid holds expire after 10 minutes and the slot becomes available again
- [ ] Booking is confirmed only by a verified Dodo webhook; a replayed webhook has no extra effect
- [ ] Invalid webhook signature returns 401 and changes nothing
- [ ] Player cancellation ≥24h before refunds in full; <24h gives no refund
- [ ] Owner cancellation always refunds in full
- [ ] Late payment on a taken slot is auto-refunded

### Owner Dashboard
- [ ] Dashboard shows correct counts, occupancy % and revenue for the selected range
- [ ] Owner sees bookings only for their own turfs

### Email Notifications
- [ ] Confirmation and cancellation emails are sent to both player and owner
- [ ] A failed email send is logged and does not fail the API request

### Admin Panel
- [ ] Only admins can access /admin routes (API returns 403 for others)
- [ ] Admin can deactivate users and turfs; deactivated users cannot log in

### Quality
- [ ] All API endpoints documented in OpenAPI
- [ ] Backend test coverage 80%+
- [ ] Frontend TypeScript strict mode passes
- [ ] Docker builds and runs successfully

---

## SPECIAL REQUIREMENTS

### Security
- [x] Rate limiting on auth endpoints (slowapi)
- [x] Input validation on all endpoints (Pydantic v2)
- [x] SQL injection prevention (SQLAlchemy ORM / bound parameters only)
- [x] XSS prevention (React escaping; no `dangerouslySetInnerHTML`)
- [x] Webhook signature verification for Dodo Payments
- [x] Ownership checks on every owner-scoped resource
- [x] Tokens (refresh, reset, verification) stored hashed, never in plain text
- [x] CORS restricted to `FRONTEND_URL`

### Integrations
- [x] Email service (SMTP) for notifications
- [x] Dodo Payments for checkout and refunds
- [ ] File upload service (post-MVP)

### Background Jobs
- [x] Every-minute job: expire stale holds, mark finished bookings `completed` (APScheduler in-process for MVP)

---

## AGENTS

> These 6 agents will build your product in parallel:

| Agent | Role | Works On |
|-------|------|----------|
| DATABASE-AGENT | Creates all models and migrations | User, tokens, Turf, TurfPricingRule, BlockedSlot, Booking, Payment, WebhookEvent |
| BACKEND-AGENT | Builds API endpoints and services | Auth, turfs, availability engine, bookings, Dodo integration, email, admin |
| FRONTEND-AGENT | Creates UI pages and components | Public search, slot picker, checkout, player/owner/admin pages |
| DEVOPS-AGENT | Sets up Docker, CI/CD, environments | docker-compose (api, web, postgres, mailpit), CI |
| TEST-AGENT | Writes unit and integration tests | Availability engine, concurrency, webhooks, refund policy |
| REVIEW-AGENT | Security and code quality audit | All code |

---

# READY?

```bash
/generate-prp INITIAL.md
```

Then:

```bash
/execute-prp PRPs/turfslot-prp.md
```
