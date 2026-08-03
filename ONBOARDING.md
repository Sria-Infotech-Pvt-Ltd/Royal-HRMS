# Royal HRMS — Team Context

> Last updated: 2026-08-03 · Branch: `demo` · Includes: Backend/31/07/2026

---

## What This Project Is

Royal HRMS is a full-stack HR management system built for Royal Staffing Services. It covers employee lifecycle (onboarding → separation), attendance, leave, payroll, recruitment, and compliance reporting.

- **Backend**: Django + Django REST Framework, served via Daphne (ASGI/WebSocket)
- **Frontend**: Next.js 15 App Router, TypeScript, custom CSS design system
- **DB**: PostgreSQL
- **Media**: Cloudinary
- **Realtime**: Django Channels (WebSocket) for notifications

---

## Running Locally

```bash
# Backend — venv is at backend/H/ (not venv/)
cd backend
H\Scripts\daphne.exe -b 0.0.0.0 -p 8000 config.asgi:application

# Frontend
cd frontend
npm run dev       # starts on port 3001 by default
```

**Important**: `NEXT_PUBLIC_API_URL` must use `localhost`, not `127.0.0.1`. Cookies won't be sent cross-origin.

After login, DevTools → Application → Cookies must show all four: `royal_hrms_auth`, `royal_hrms_user`, `royal_access_token`, `royal_refresh_token`.

---

## Project Structure

```
backend/
  apps/
    accounts/      auth, users, roles, permissions, audit, bulk import
    announcements/
    branch/        branch CRUD, geofencing
    recruitment/   candidates, interviews, pipeline
    hrms/          employees, attendance, leave, payroll, expenses, docs
    payroll/       payroll cycles, payslips, ECR, salary config
    voice_commands/
  core/
    responses.py   shared success()/error() — always import from here
    permissions.py shared DRF permission classes
  config/          Django settings + root URLs

frontend/
  app/             Next.js App Router pages only — no logic here
  components/      reusable UI only
  hooks/           useFetch, useCurrentUser, usePermission, useVoiceCommand…
  lib/api/
    endpoints.ts   ALL API paths — never write inline strings
    client.ts      axios instance (withCredentials: true)
  types/           all TypeScript interfaces
  proxy.ts         route guard (reads signed JWT cookie, not royal_hrms_user)
```

---

## Key Rules (from CLAUDE.md)

- Never store JWT tokens in localStorage — httpOnly cookies only
- Never use `CORS_ALLOW_ALL_ORIGINS = True`
- Never use `fail_silently=True` in email sending
- Never use `from django.core.mail import send_mail` — use `send_template_email` from `accounts.utils`
- Never define `success()`/`error()` locally — import from `core/responses.py`
- Never write inline API paths — all paths go in `lib/api/endpoints.ts`
- Never write manual `useState + useEffect + fetch` — use the `useFetch` hook
- `any` is banned in TypeScript
- All list endpoints must be paginated (page_size=20)
- All new Django models need `db_table`, `created_at`, `updated_at`, `__str__`
- Run `makemigrations` before pushing any model change

---

## Recent Features (as of 2026-08-03)

### Payroll — ECR Download
- **Endpoint**: `GET /api/payroll/cycles/<id>/ecr/` — returns a styled `.xlsx` with all EPFO columns
- **Page**: `/dashboard/payroll/runs/[id]` — payroll run detail with summary cards + Download ECR button
- Paid/closed cycles in the payroll list now navigate to the detail page; in-progress cycles open the wizard; cancelled cycles are non-clickable
- ECR uses `ROUND_HALF_UP` rounding on all wage figures (not `int()` truncation)
- Branch-scoped: non-superuser HR can only download their own branch's ECR

### Payroll — Configurable Statutory Rates
- `PayrollSettings` now has `eps_rate` (8.33%), `edli_rate` (0.5%), `edli_wage_ceiling` (₹15,000), `epf_admin_rate` (0.5%)
- Editable from **Payroll Settings UI** without code changes when law changes
- All rate fields validated server-side: must be 0–100 range

### Employees — UAN & Aadhar Name
- `EmployeeProfile` has `uan_number` (12-digit, validated) and `name_as_per_aadhar`
- HR enters these at **onboarding approval time** (they have the Aadhaar scan in the same drawer)
- Also editable from **Employee Profile page** (EPF / Statutory section)
- Bulk import accepts `UAN`, `UAN Number`, `Name as per Aadhar`, `Aadhar Name` column headers

### Bulk Import Improvements
- `annual_ctc` column strips Indian comma formatting before parse (`10,00,000` → `Decimal("1000000")`)
- Invalid CTC values now surface as a row error (not a silent warning)

### Leave / Expense / Attendance / Recruitment — Approval Scoping (31 Jul)
- HR users now see only employees assigned to them (`employee.hr`), not the whole branch. Branch-wide fallback only for unassigned employees.
- Managers see both their L1 queue and any L2 requests assigned to them (scopes ORed, not short-circuited).
- Recruitment views now branch-scoped for non-admins.
- See `frontend/TEAMCONTEXT.md` for full session detail.

### Attendance
- `ClockWidget` now passes `AttendanceMode = "office"` to the punch function

---

## Active Branches

| Branch | Purpose |
|---|---|
| `demo` | Main integration branch — all features merge here |
| `frontendtest` | Frontend testing — kept in sync with demo |

---

## Migrations Applied (local DB)

| Migration | What it does |
|---|---|
| `accounts/0048` | Adds `uan_number`, `name_as_per_aadhar` to `EmployeeProfile` |
| `payroll/0008` | Adds `eps_rate`, `edli_rate`, `edli_wage_ceiling`, `epf_admin_rate` to `PayrollSettings` |

---

## Repo

`github.com/Sriainfotech/Royal-HRMS` — branch `demo`
