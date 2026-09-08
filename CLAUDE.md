# CLAUDE.md — Royal HRMS Engineering Rules

This file is read by Claude Code before every session.
Follow every rule here without exception.
If a rule conflicts with a user request, flag it before proceeding.

---

## 0. Before Writing Any Code

1. Read the relevant existing files before creating or editing anything
2. Check if a utility, hook, or component already exists before creating a new one
3. Never create a file without knowing where it belongs in the structure below
4. If unsure where something goes — ask, do not guess

---

## 1. Project Structure — Never Deviate From This

```
backend/
  apps/
    accounts/          auth, users, roles, permissions, audit
    announcements/     announcements only
    branch/            branch management only
    recruitment/       candidates, interviews, emails only
    hrms/              employees, attendance, leave, payroll, expenses,
                       referrals, documents, separation, notifications
  core/
    responses.py       shared response helpers — success(), error(), etc.
    permissions.py     shared DRF permission classes
    pagination.py      shared pagination config
    exceptions.py      custom exception handler
  config/
    settings.py        Django settings
    urls.py            root URL config

frontend/
  app/                 Next.js App Router pages only — no logic here
  components/          reusable UI components only
  hooks/               custom React hooks only (useFetch, useAuth, etc.)
  lib/
    api/
      client.ts        axios instance — one place, one config
      endpoints.ts     ALL API path constants — no inline strings anywhere
    auth.ts            auth state (Zustand or Context)
  types/               all TypeScript interfaces and types
  proxy.ts             Next.js route proxy — THIS FILE, THIS NAME
```

### Rules

- Do not add files to the repo root unless it is a config file (`.gitignore`, `docker-compose.yml`, etc.)
- Do not add `.bak`, `_backup`, `_old` files — use git for history
- Do not commit build artifacts: `eslint_output.txt`, `lint_output.txt`, `*.log`
- Do not create a new Django app without a clear single-domain reason
- Do not add business logic to the `app/` folder — it belongs in `hooks/` or `lib/`

---

## 2. What Must Never Be Committed to Git

Add these to `.gitignore` immediately if missing:

```
# Python
venv/
env/
.venv/
backend/H/
**/__pycache__/
**/*.pyc
*.pyo
.env

# Logs — never ever in git
logs/
*.log
auth.log

# Build and IDE artifacts
eslint_output.txt
lint_output.txt
.next/
node_modules/
dist/
build/
coverage/

# Backup files
*.bak
*_backup.*
*_old.*

# Secrets
.env.local
.env.production
*.pem
*.key
```

**Never commit:**
- Any file containing a password, secret key, API key, or token
- Any log file (auth.log, error.log, debug.log)
- Any Python virtual environment directory
- Any compiled binary or executable
- Any `.env` file (only `.env.example` is allowed)

---

## 3. Security Rules — Non-Negotiable

### Tokens and Auth

- **Never store JWT tokens in localStorage** — use httpOnly; Secure; SameSite=Lax cookies only
- **Never expose tokens in API response bodies** — set them as cookies in the response headers
- **Never read tokens from cookies in JavaScript** — httpOnly cookies are sent automatically by the browser
- The axios client must always have `withCredentials: true`
- **Never use `secure=True` unconditionally on `set_cookie`** — always use `secure=not settings.DEBUG` so cookies are stored and sent in local development over HTTP. In production `DEBUG=False` so `secure` evaluates to `True` automatically.
- **The API base URL in the frontend must use `localhost` not `127.0.0.1`** — the browser treats them as different sites and will not send cookies across them, breaking the entire auth cookie flow.

### CORS

- **Never set `CORS_ALLOW_ALL_ORIGINS = True`** in any environment
- Always use `CORS_ALLOWED_ORIGINS = [list of known domains]`
- Always set `CORS_ALLOW_CREDENTIALS = True`

### Secrets and Config

- **Never hardcode** company names, email addresses, amounts, or configuration values in code
- Always read from the database model (Company, SMTPConfig) or environment variables
- Never hardcode: `'Royal Staffing Services LLP'` — use `Company.objects.first().name`
- Never hardcode: bonus amounts, email addresses, domain names

### Email Security

- **Never use `fail_silently=True`** — always catch exceptions and log/record failures
- Always record email status correctly: STATUS_SENT only when no exception was raised

### Input Validation

- All API inputs validated server-side with serializer validators — never trust client data
- All file uploads validated for type (whitelist only) and size (max 5MB)
- No raw SQL string concatenation — parameterised queries or ORM only

---

## 4. Shared Utilities — Always Use These, Never Duplicate

### Backend Response Helpers

All views in all apps must import from `core/responses.py`:

```python
from core.responses import success, error, first_error, get_client_ip
```

**Never** define `success()`, `error()`, `ok()`, `err()`, `_first_error()`,
or `get_client_ip()` inside any app's `views.py`.
**Never** rename these helpers — they are always `success` and `error`.

### Backend Email Sending

All apps must send email using the project's shared SMTP utility:

```python
from apps.accounts.utils import send_template_email
```

**Never** use `from django.core.mail import send_mail` in any app.
Django's built-in `send_mail` ignores the admin-configured SMTP settings.

### Frontend API Paths

All API endpoint paths must come from `lib/api/endpoints.ts`:

```typescript
import { API } from "@/lib/api/endpoints"
apiClient.get(API.candidates.list)
```

**Never** write inline API path strings like `apiClient.get("/candidates/")`.
If a path does not exist in `endpoints.ts`, add it there first.

### Frontend Data Fetching

All data fetching must use the `useFetch` hook:

```typescript
import { useFetch } from "@/hooks/useFetch"
const { data, loading, error, refetch } = useFetch<Candidate[]>(API.candidates.list)
```

**Never** write `useState` + `useEffect` + `try/catch` + `setLoading` in a page component.
That pattern is what `useFetch` replaces.

---

## 5. Naming Conventions

### Python (Backend)

| Thing | Convention | Example |
|-------|-----------|---------|
| Files and folders | `snake_case` | `user_profile.py` |
| Classes | `PascalCase` | `CandidateListView` |
| Functions and variables | `snake_case` | `get_client_ip()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_LOGIN_ATTEMPTS = 5` |
| Private helpers | leading underscore | `_build_context()` |
| URL names | `snake_case` with hyphens in URL | `name="candidate-list"` |

### TypeScript (Frontend)

| Thing | Convention | Example |
|-------|-----------|---------|
| Files (components) | `PascalCase.tsx` | `CandidateCard.tsx` |
| Files (hooks) | `camelCase.ts` | `useFetch.ts` |
| Files (lib/utils) | `camelCase.ts` | `formatDate.ts` |
| Components | `PascalCase` | `function CandidateCard()` |
| Hooks | `use` prefix | `function useFetch()` |
| Variables and functions | `camelCase` | `const candidateList` |
| Constants | `UPPER_SNAKE_CASE` | `const MAX_FILE_SIZE = 5_000_000` |
| Types and interfaces | `PascalCase` | `interface Candidate {}` |

### Specific Rules

- The Next.js proxy file is **always** named `proxy.ts` at the frontend root (Next.js 16 renamed Middleware to Proxy)
- `proxy.ts` **always** uses a named export: `export function proxy(request: NextRequest) { ... }`
- The `config` object in `proxy.ts` must always include a `matcher` array
- Django app folders **always** use `snake_case`
- No abbreviations in names: `btn`, `inp`, `usr`, `req`, `res` are not allowed as variable names
- Boolean variables start with `is`, `has`, `can`, `should`:
  `is_active`, `has_permission`, `can_delete`, `should_notify`

---

## 6. Code Organisation Rules

### Functions and Files

- Maximum function length: **50 lines** — if longer, extract to a helper
- Maximum file length: **300 lines** — if longer, split by domain
- One class per file for complex classes
- A file that imports from more than 5 other files is probably doing too much

### Django Views

- Each Django app's `views.py` must handle **only that app's domain**
- If a view file exceeds 300 lines, split it:

```
accounts/views/
    auth.py
    roles.py
    settings.py
    documents.py
```

- Every view class must declare `permission_classes` explicitly — never rely on defaults
- Every list view must have pagination — no list endpoint returns all records

### React Components

- A component that manages more than **5 pieces of state** should be split
- A component file longer than **200 lines** should be split
- No data fetching inside a component — fetch in a hook, pass data as props
- No API calls directly in a page file — they belong in a hook in `hooks/`
- Props must be typed — no untyped props ever

### Logic Separation

- Business logic goes in services/utilities — never in views or components
- UI rendering goes in components — never mixed with data fetching logic
- Configuration values go in settings/constants — never hardcoded inline

---

## 7. Django-Specific Rules

### Migrations

- Never edit a migration file that has already been committed and pushed
- Always run `makemigrations` after any model change before pushing
- Every `Model.Meta` class must define `db_table` explicitly
- Data migrations use `get_or_create` — never bare `create()` in migrations

### Models

- Every model must have `created_at` and `updated_at` fields
- Primary keys are always `UUIDField(default=uuid.uuid4)`
- PAN, Aadhaar, bank account numbers must be noted as requiring encryption
- No business logic in `save()` — use signals or service functions
- Every model must have `__str__` defined

### API and Serializers

- Every endpoint must return responses in the standard envelope:
```python
{"success": bool, "message": str, "data": any}
```
- Never return raw serializer data without the envelope
- All list endpoints must use `PageNumberPagination` with `page_size = 20`
- Serializer `Meta.fields` must list fields explicitly — never use `"__all__"`

### Logging

- Every app uses its own logger: `logger = logging.getLogger(__name__)`
- **Never** use `logging.getLogger('accounts')` in another app
- Log levels: `DEBUG` for development details, `INFO` for business events,
  `WARNING` for unexpected but handled situations, `ERROR` for failures
- Never log passwords, tokens, full request bodies, or PAN/Aadhaar values

---

## 8. TypeScript-Specific Rules

### Types

- `any` is **banned** — use `unknown` and narrow, or define the correct type
- `noImplicitAny: true` is set in `tsconfig.json` — never disable it
- All API response shapes must be typed in `types/`
- All component props must be typed with an `interface`

### ESLint

- `eslint_output.txt` must never exist in the repo
- ESLint errors must be fixed — never suppressed with `// eslint-disable`
- Only exception: a single-line `// eslint-disable-next-line` with a comment explaining why

### Patterns

- No `!` non-null assertions — narrow the type with an explicit check instead
- No `as SomeType` type casts without a comment explaining why it is safe
- All `useEffect` dependencies must be complete — never suppress the exhaustive-deps warning

---

## 9. Frontend Security Rules

### Next.js Proxy

- Route permission enforcement lives in `proxy.ts` (named export `proxy`)
- The `matcher` config must include all protected routes
- Proxy reads permissions from a **signed** source (JWT claims) — never from an unsigned cookie value
- **Route permission checks in `proxy.ts` must read role and permissions from the signed httpOnly JWT cookie set by the backend, not from the `royal_hrms_user` cookie which is client-writable and unsigned.** Reading from an unsigned cookie allows any user to edit their permissions in the browser and bypass frontend route guards. The backend API will still reject the request but any server-side rendered content before the API call will be exposed.
- A user with role `employee` must not be able to see the content of `/dashboard/settings` even if they navigate there directly

### Cookies

- Access token: `httpOnly; Secure; SameSite=Lax; max-age=900`
- Refresh token: `httpOnly; Secure; SameSite=Lax; max-age=604800`
- No sensitive data in non-httpOnly cookies
- No sensitive data in localStorage or sessionStorage
- **After login, all four of these cookies must be present in DevTools → Application → Cookies:** `royal_hrms_auth`, `royal_hrms_user`, `royal_access_token`, `royal_refresh_token`. If any are missing the auth loop will break — check `secure=not settings.DEBUG` and that `NEXT_PUBLIC_API_URL` uses `localhost` not `127.0.0.1`.

### External Resources

- External CDN resources must be pinned to a specific version — never `@latest`
- Self-host fonts using `next/font` — never `@import` from Google Fonts in CSS
- Add `integrity` attribute to any external script tag

---

## 10. What to Check Before Every Pull Request

Run this checklist before marking any PR as ready:

```
□ No new files in the repo root (unless config files)
□ No .env, .log, .bak, or venv files changed
□ No secrets, passwords, or tokens in any file
□ No inline API path strings — all paths from endpoints.ts
□ No new success()/error() helpers defined locally — use core/responses.py
□ No send_mail import — use send_template_email from accounts.utils
□ No localStorage.setItem for tokens
□ No CORS_ALLOW_ALL_ORIGINS = True
□ No fail_silently=True
□ No any types in TypeScript
□ No ESLint errors
□ All new list endpoints have pagination
□ All new Django models have db_table, created_at, updated_at, __str__
□ Migration files created for all model changes
□ useFetch hook used instead of manual useState/useEffect fetch pattern
□ New reusable UI extracted to components/
□ New business logic extracted to hooks/ or utils/
□ Logger uses getLogger(__name__) not getLogger('accounts')
□ No 127.0.0.1 in any frontend config — use localhost
□ No secure=True without not settings.DEBUG guard on set_cookie calls
□ All four auth cookies visible in DevTools after login before marking auth work done
```

---

## 11. When Adding a New Feature

Follow this order — no skipping steps:

1. Check if a similar feature already exists — read before writing
2. Identify where in the structure the code belongs (see Section 1)
3. Add the API endpoint path to `lib/api/endpoints.ts` first
4. Write the backend serializer and view
5. Write the migration if models changed
6. Write the frontend hook using `useFetch`
7. Write the component using the hook
8. Run the PR checklist from Section 10

---

## 12. When Fixing a Bug

1. Reproduce the bug by reading the code — understand it fully before touching anything
2. Fix only the bug — do not refactor unrelated code in the same PR
3. If the bug reveals a pattern problem (e.g., same bug exists in 4 places), fix the root cause, not each instance individually
4. Add a comment explaining why the fix works if it is not obvious

---

*This file is law for this codebase.
No exceptions without a team decision documented in a PR comment.*
