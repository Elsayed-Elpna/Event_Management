# Event Management Backend

A backend service for selling event tickets with a smooth reservation and purchase
experience. It prevents oversell under concurrency, gives organizers control over
capacity and refunds, and keeps a full audit trail of every inventory change.

Built with **Django 6**, **Django REST Framework**, **PostgreSQL**, **Redis** and
**Celery / Celery Beat**, packaged to run fully in **Docker**.

## Tech Stack

| Layer      | Technology                          |
| ---------- | ----------------------------------- |
| API        | Django 6, Django REST Framework     |
| Auth       | JWT (`rest_framework_simplejwt`)    |
| Database   | PostgreSQL                          |
| Broker     | Redis                               |
| Jobs       | Celery worker + Celery Beat         |
| Payments   | Paymob (simulated capture)          |
| Docker     | Dockerfile + docker-compose         |

## Quick Start (Docker)

### 1. Prerequisites

- Docker with Docker Compose
- A `.env` file in the project root. Copy this as a starting point:

```dotenv
SECRET_KEY=change-me
DEBUG=True
DB_NAME=event_db
DB_USER=event_user
DB_PASSWORD=change-me
DB_HOST=db
DB_PORT=5432
REDIS_URL=redis://redis:6379/0

REFUND_CUTOFF_HOURS=48

PAYMOB_BASE_URL=https://accept.paymob.com
PAYMOB_SECRET_KEY=your-paymob-secret-key
PAYMOB_PUBLIC_KEY=your-paymob-public-key
PAYMOB_HMAC_SECRET=your-paymob-hmac-secret
PAYMOB_INTEGRATION_ID=your-integration-id
PAYMOB_NOTIFICATION_URL=http://localhost:8000/api/payments/webhook/
PAYMOB_REDIRECTION_URL=http://localhost:8000
```

### 2. Bring up the whole stack

```bash
docker compose up -d --build
```

Services start in dependency order using healthchecks (no fixed sleeps):

| Service        | Purpose                       |
| -------------- | ----------------------------- |
| `db`           | PostgreSQL (named volume)     |
| `redis`        | Celery broker / result store |
| `backend`      | Django API on port 8000      |
| `celery-worker`| Runs background jobs         |
| `celery-beat`  | Schedules recurring jobs      |

### 3. Verify it is healthy

```bash
curl http://localhost:8000/health/
# {"database":"ok","redis":"ok","status":"ok"}

docker compose ps
# event_backend   Up ... (healthy)
```

### 4. Apply migrations (first run)

```bash
docker compose exec backend python manage.py migrate
```

### 5. Create a superuser (optional, for the admin)

```bash
docker compose exec backend python manage.py createsuperuser
```

## Running Locally (without Docker)

```bash
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt

python manage.py migrate
python manage.py runserver

# in separate terminals
python -m celery -A core worker -l info
python -m celery -A core beat -l info
```

The Postgres database must be reachable (see `.env`).

## Authentication

All endpoints except `/health/`, `/api/register/` and the payment webhook require a
JWT `Authorization: Bearer <token>` header.

```bash
# register
curl -X POST http://localhost:8000/api/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"TestPassword123","is_event_maker":true}'

# obtain token
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"TestPassword123"}'

# refresh token
curl -X POST http://localhost:8000/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"<refresh_token>"}'
```

## API Reference

All routes are prefixed with `/api`.

| Method | Endpoint                              | Auth | Description                                      |
| ------ | ------------------------------------- | ---- | ------------------------------------------------ |
| GET    | `/health/`                            | No   | Health check (DB + Redis)                        |
| POST   | `/api/register/`                      | No   | Create user                                      |
| POST   | `/api/token/`                         | No   | Login -> access/refresh tokens                   |
| POST   | `/api/token/refresh/`                 | No   | Refresh access token                             |
| GET    | `/api/profile/`                       | Yes  | Current user profile                             |
| POST   | `/api/events/`                        | Yes  | Create event (event maker with active sub)       |
| GET    | `/api/events/`                        | Yes  | List events (attendees see published only)       |
| GET    | `/api/events/<event_id>/`             | Yes  | Event details                                    |
| PATCH  | `/api/events/<event_id>/update/`      | Yes  | Update event (owner)                             |
| POST   | `/api/events/<event_id>/publish/`     | Yes  | Publish event (owner)                            |
| POST   | `/api/events/<event_id>/ticket/`      | Yes  | Create ticket type (draft only)                  |
| PATCH  | `/api/events/<ticket_type_id>/update-ticket/` | Yes | Update ticket type (draft only)          |
| POST   | `/api/reservations/`                  | Yes  | Create reservation (hold)                        |
| GET    | `/api/reservations/me/`               | Yes  | List my reservations                             |
| POST   | `/api/reservations/<id>/cancel/`      | Yes  | Cancel a held reservation                        |
| POST   | `/api/orders/create/`                 | Yes  | Create order (requires `idempotency_key`)        |
| GET    | `/api/orders/`                        | Yes  | List my orders                                   |
| POST   | `/api/orders/<id>/payment/`           | Yes  | Initiate payment -> checkout URL                 |
| POST   | `/api/orders/<id>/refund/`            | Yes  | Full-order refund -> `201` with `PENDING` status |
| POST   | `/api/subscriptions/`                 | Yes  | Create subscription                              |
| GET    | `/api/subscriptions/me/`              | Yes  | My subscription                                  |
| GET    | `/api/balance/`                       | Yes  | My balance (sales + totals)                      |
| POST   | `/api/payments/webhook/`              | No   | Paymob webhook (HMAC verified)                   |

### Example: reservation -> order -> payment

```bash
# 1. reserve (returns reservation_id and expires_at)
curl -X POST http://localhost:8000/api/reservations/ \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"ticket_type": 1, "quantity": 2}'

# 2. create order (idempotent per idempotency_key)
curl -X POST http://localhost:8000/api/orders/create/ \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"reservation_id": 1, "idempotency_key": "<any-uuid>"}'

# 3. initiate payment -> get checkout_url
curl -X POST http://localhost:8000/api/orders/1/payment/ \
  -H "Authorization: Bearer <token>"

# 4. refund (full order)
curl -X POST http://localhost:8000/api/orders/1/refund/ \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"reason":"customer request"}'
```

## Core Flows (User Journeys)

**Browse and reserve**

1. User selects a ticket type and quantity.
2. The system creates a short-lived reservation (`HELD`) and decrements inventory.
3. User receives `reservation_id` and `expires_at` (default hold: 10 minutes,
   configurable per event via `hold_duration`).

**Complete purchase**

1. User creates an order, supplying an `idempotency_key`.
2. User pays via the Paymob checkout URL.
3. Paymob calls the webhook -> payment/order become `PAID`, reservation becomes
   `CONFIRMED`, an organizer balance entry is recorded, audit entries are written.

**Payment initiation outage**

- If Paymob is unreachable during checkout, the API returns a retryable error
  and nothing partial is persisted; the order stays `PENDING` and payment can
  be re-initiated (first writer wins if two attempts race).

**Payment failure**

- The reservation stays `HELD` until it expires or the user cancels it.
- A retry with the same `idempotency_key` returns the same order (idempotent).

**Reservation expiry**

- The background job marks expired holds as `EXPIRED` and restores inventory.
- Expired reservations can never be confirmed or paid.

**Refund (full order, asynchronous)**

1. Organizer, buyer, or staff issues a full refund. The API validates the order
   and creates a `Refund` with status `PENDING`, then responds immediately.
2. A Celery task performs the Paymob call outside any database transaction:
   - On success: payment/order become `REFUNDED`, inventory is restored, the
     reservation is `CANCELLED` (the ticket is revoked), the organizer balance
     entry is zeroed, and audit entries are written.
   - On transient provider errors: the task retries with exponential backoff;
     after exhausting retries (or a permanent provider rejection) the refund is
     marked `FAILED` with an audit entry, and the order stays `PAID`.
3. Refunds are **blocked for everyone** within `REFUND_CUTOFF_HOURS` of the
   event start (default 48 h) and after the event has started.

## Business Rules

- **Capacity** is set per ticket type and is immutable once the event is published.
- **Available inventory** is the sellable count; holds reduce it and expiry/cancel/refund restore it.
- **Price** is stored in **cents** (`price_cents`).
- **Idempotent orders** - one order per `idempotency_key`, enforced by a unique DB constraint.
- **Zero tolerance for oversell** - reservations serialize on a Postgres row lock.
- **Refunds** are full-order only, processed asynchronously by a background
  task (no DB locks are held across Paymob HTTP calls), restore inventory,
  cancel the reservation (revoking the ticket), and zero the balance entry.
- **Refund cutoff** - refunds close for everyone within `REFUND_CUTOFF_HOURS`
  hours before the event starts (env-tunable, default 48) and stay closed
  afterwards.
- **No raw payment data is stored** - only provider references/transaction ids
  (exposed via `/api/balance/` for reconciliation).

## Background Jobs (Celery Beat)

| Task                             | Schedule | What it does                          |
| -------------------------------- | -------- | ------------------------------------- |
| `jobs.tasks.expire_reservations` | 30 s     | Expire stale holds, restore inventory |
| `jobs.tasks.fail_expired_orders` | 30 s     | Fail orders/payments of expired holds |
| `jobs.tasks.finish_events`       | 60 s     | Mark finished events `FINISHED`      |
| `jobs.tasks.expire_subscriptions`| 1 h      | Expire subscriptions                  |

## Concurrency Test (Zero Oversell)

`reservations/tests.OversellConcurrencyTest` launches 20 threads racing to reserve
10 tickets and asserts that exactly 10 succeed, 10 are rejected, and inventory never
goes negative.

```bash
docker compose exec backend python manage.py test reservations.tests.OversellConcurrencyTest --noinput
```

Requires PostgreSQL (row locks), so run it while the `db` service is up.

## Metrics and How They Are Measured

| Metric                                        | How it is measured                                                        |
| --------------------------------------------- | ------------------------------------------------------------------------- |
| Remaining inventory per ticket type           | `TicketType.available_inventory` column, exposed in the ticket type API   |
| Count of active reservations                  | `Reservation.objects.filter(status=HELD).count()`                         |
| Idempotency collisions (duplicate keys)       | Requests that hit the existing-key lookup / `IntegrityError` fallback in `orders.service.create_order` |
| Oversell incidents (target: zero)             | `OversellConcurrencyTest`; invariant `available_inventory >= 0`           |
| Reservation expiry lag                        | `now - expires_at` for holds swept by `expire_reservations` (logged per run) |
| Checkout latency (reserve < 500 ms, confirm < 2 s) | API response timing on `/api/reservations/` and the payment webhook       |

## Operational Notes

**View the audit log for a given reservation or order**

Via Django admin (`/admin/audit/auditlog/`), filter by action and entity type, or use:

```bash
docker compose exec backend python manage.py shell -c "from audit.models import AuditLog; print(list(AuditLog.objects.filter(entity_type='Reservation', entity_id=1)))"
docker compose exec backend python manage.py shell -c "from audit.models import AuditLog; print(list(AuditLog.objects.filter(entity_type='Order', entity_id=1)))"
```

Every inventory change and lifecycle event (`reserve`, `confirm`, `expire`,
`refund`) is recorded with a timestamp, actor and reason.

**Manually re-run the expiry job (during testing)**

```bash
docker compose exec backend python manage.py shell -c "from jobs.services.expiry_service import expire_reservations; print(expire_reservations())"
docker compose exec backend python manage.py shell -c "from jobs.services.expiry_service import fail_expired_orders; print(fail_expired_orders())"
```

**Inspect Docker logs for the API and database**

```bash
docker compose logs -f backend
docker compose logs -f db
docker compose logs -f celery-worker
docker compose logs -f celery-beat
```

## Testing

```bash
docker compose exec backend python manage.py test --noinput
```

Notes:

- Tests require PostgreSQL, so start `db` first.
- Use `--noinput` in non-interactive shells so the test database is recreated automatically.
- `--keepdb` speeds up repeated runs by reusing the test database (drop
  `test_event_db` manually if migrations changed shape).
- The suite covers the full refund lifecycle including the 48-hour cutoff,
  provider failure paths, subscription checkout outages, and a concurrency
  zero-oversell race.

## Project Structure

```
accounts/       Users, registration, profile, JWT
events/         Events, ticket types (capacity/price in cents)
reservations/   Reservation holds, expiry, cancellation
orders/         Idempotent order creation, payment initiation, refunds
payments/       Payment/refund models, Paymob integration + webhook, async refund task
subscriptions/  Organizer subscriptions
balance/        Organizer balance from paid orders (sales ledger + totals)
audit/          AuditLog for every inventory/order lifecycle event
jobs/           Celery tasks + expiry services
common/         Shared base model
core/           Project settings, URL routing, Celery app, health endpoint
```
