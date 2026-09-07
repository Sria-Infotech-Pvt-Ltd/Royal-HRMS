# Server Deployment Context --- Hostinger KVM 4

> **Purpose:** This document describes the current production VPS so a
> developer/AI assistant can design and deploy a **new application
> without disturbing the existing CareerBuddy application**.
>
> **Important:** This document intentionally excludes passwords, API
> keys, Django secrets, database credentials, tokens, and `.env` values.

------------------------------------------------------------------------

## 1. Critical deployment rule

### 🔴 DO NOT TOUCH existing production resources

The following belong to the existing application and must not be
deleted, renamed, restarted, reconfigured, or reused without explicit
approval:

-   Existing application directory:
    -   `/var/www/careerbuddy4u/app`
-   Existing Python virtual environment:
    -   `/var/www/careerbuddy4u/app/.venv`
-   Existing Supervisor program:
    -   `careerbuddy_daphne`
-   Existing application port:
    -   `127.0.0.1:8000`
-   Existing MySQL database:
    -   `business_english_lms`
-   Existing Redis:
    -   `127.0.0.1:6379`
-   Existing Nginx site:
    -   `/etc/nginx/sites-available/careerbuddy4u`
-   Existing production domain:
    -   `careerbuddy4u.com`
    -   `www.careerbuddy4u.com`
-   Existing application's `.env`:
    -   `/var/www/careerbuddy4u/app/.env`
-   Existing application logs:
    -   `/var/log/careerbuddy_daphne.err.log`
    -   `/var/log/careerbuddy_daphne.out.log`

### 🟢 New application isolation requirements

The new application should have:

-   A separate application directory
-   A separate Python virtual environment
-   A separate Linux service/process
-   A separate PostgreSQL database
-   A separate PostgreSQL database user
-   A separate local application port
-   A separate Nginx server block
-   A separate domain/subdomain
-   Separate logs
-   Separate environment configuration
-   No dependency on the existing application's `.venv`
-   No dependency on the existing MySQL database
-   No reuse of the existing Redis database unless explicitly designed
    and isolated

Do not deploy the new application into `/var/www/careerbuddy4u/app`.

------------------------------------------------------------------------

# 2. VPS / Hostinger

-   Provider: Hostinger
-   VPS plan: KVM 4
-   Hostname: `srv1795199`
-   Hostinger hostname shown: `srv1795199.hstgr.cloud`
-   IPv4: `2.25.73.246`
-   OS: Ubuntu 24.04.4 LTS
-   Architecture: x86_64
-   Virtualization: KVM
-   Kernel: Linux 6.8.0-124-generic
-   Hardware presented by virtualization: QEMU / AMD EPYC 9354P model

------------------------------------------------------------------------

# 3. Compute resources

From the server inspection:

-   CPU: 4 vCPUs
-   RAM: approximately 15 GiB
-   Current available RAM at inspection: approximately 14 GiB
-   Swap: **0 B / no swap configured**
-   Root filesystem: approximately 193 GB
-   Used disk: approximately 8.7 GB
-   Available disk: approximately 185 GB
-   Root filesystem type: ext4

At inspection time, resource usage was low:

-   CPU: approximately 2%
-   Memory: approximately 10%
-   Disk: approximately 5%

These are point-in-time observations, not capacity guarantees.

------------------------------------------------------------------------

# 4. Existing application

## Application

Existing application appears to be a Python/Django application.

Location:

``` text
/var/www/careerbuddy4u/app
```

Project structure observed includes:

``` text
manage.py
business_english_lms/
accounts_app/
career_app/
employer_portal/
jam_app/
jobs_app/
users/
core/
activities/
templates/
staticfiles/
media/
protected_media/
.venv/
.git/
requirements.txt
```

The project contains multiple Django apps/modules and appears to be a
substantial production application.

## Python environment

Virtual environment:

``` text
/var/www/careerbuddy4u/app/.venv
```

Python:

``` text
3.12.3
```

Installed Django:

``` text
5.2.17
```

Installed Daphne:

``` text
4.2.2
```

Installed Channels:

``` text
4.3.2
```

Installed mysqlclient:

``` text
2.2.8
```

The project's `requirements.txt` declares Django, mysqlclient,
python-decouple, Pillow, Daphne, Channels, requests, PDF/DOCX libraries,
Razorpay, phonenumbers, etc.

## Existing application server

Supervisor configuration shows:

``` text
[program:careerbuddy_daphne]

command=/var/www/careerbuddy4u/app/.venv/bin/daphne -b 127.0.0.1 -p 8000 business_english_lms.asgi:application

directory=/var/www/careerbuddy4u/app

user=www-data

autostart=true
autorestart=true
```

Therefore the existing application is served by Daphne on:

``` text
127.0.0.1:8000
```

Supervisor configuration file:

``` text
/etc/supervisor/conf.d/careerbuddy.conf
```

Supervisor version:

``` text
4.2.5
```

Do not stop/restart/reload this process during new application
deployment.

------------------------------------------------------------------------

# 5. Existing Git repository

The existing application has a Git remote:

``` text
origin  github-careerbuddy:srinivas1543/Career_Buddy_LMS.git
```

This indicates the existing application is associated with a GitHub
repository.

Do not perform `git pull`, `git reset`, `git checkout`, or other
repository-changing operations on the existing production directory
unless explicitly authorized.

------------------------------------------------------------------------

# 6. Existing environment configuration

The existing application has:

``` text
/var/www/careerbuddy4u/app/.env
```

Observed variable names include:

``` text
SECRET_KEY
SARVAM_API_KEY
DEBUG
DB_NAME
DB_USER
DB_PASSWORD
DB_HOST
DB_PORT
EMAIL_BACKEND
EMAIL_HOST
EMAIL_PORT
EMAIL_USE_TLS
EMAIL_USE_SSL
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
DEFAULT_FROM_EMAIL
ALLOWED_HOSTS
PAYMENT_MODE
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
```

**Secret values are intentionally not included in this document.**

Existing database host was confirmed as:

``` text
DB_HOST=localhost
```

Existing database name was confirmed as:

``` text
DB_NAME=business_english_lms
```

Do not expose or copy the existing `.env` into the new application.

------------------------------------------------------------------------

# 7. Existing database and cache

## MySQL

MySQL is installed and running.

Observed listener:

``` text
127.0.0.1:3306
```

Existing application database:

``` text
business_english_lms
```

The MySQL root account does not permit passwordless login through:

``` text
mysql
```

A password-authenticated MySQL account is therefore used for database
administration/application access.

**Do not reset the MySQL root password.**

**Do not modify or delete `business_english_lms`.**

## Redis

Redis is installed and running.

Observed listeners:

``` text
127.0.0.1:6379
[::1]:6379
```

Redis is therefore local-only based on the observed listeners.

Do not flush, restart, or reconfigure the existing Redis service without
confirming its use by the existing application.

------------------------------------------------------------------------

# 8. PostgreSQL

PostgreSQL is **not currently installed as a systemd service**.

A check of:

``` text
systemctl status postgresql --no-pager
```

returned:

``` text
Unit postgresql.service could not be found.
```

### Planned use

The new application will use **PostgreSQL**, not the existing MySQL
database.

PostgreSQL should be installed and configured only after:

1.  The new application's requirements are reviewed.
2.  A backup/snapshot strategy is confirmed.
3.  Resource impact is considered.
4.  A dedicated database and database user are designed.

Recommended isolation:

``` text
PostgreSQL
├── new_application_database
└── new_application_user
```

Do not use:

``` text
business_english_lms
```

for the new application.

------------------------------------------------------------------------

# 9. Nginx

Nginx is installed and running.

## Enabled sites

`/etc/nginx/sites-enabled/` contains:

``` text
careerbuddy4u -> /etc/nginx/sites-available/careerbuddy4u
default       -> /etc/nginx/sites-available/default
grafana       -> /etc/nginx/sites-available/grafana
```

## Available sites

`/etc/nginx/sites-available/` contains:

``` text
careerbuddy
careerbuddy4u
default
grafana
```

Important observation:

``` text
careerbuddy
```

is present in `sites-available` but was **not observed as an enabled
symlink** in `sites-enabled`.

Do not enable or modify it without investigation.

## Existing CareerBuddy Nginx routing

The existing production configuration contains:

``` text
careerbuddy4u.com
www.careerbuddy4u.com
        ↓
Nginx
        ↓
http://daphne
        ↓
127.0.0.1:8000
```

HTTP:

``` text
port 80
```

redirects to HTTPS.

HTTPS:

``` text
port 443
```

uses Let's Encrypt certificates for:

``` text
careerbuddy4u.com
```

Static files:

``` text
/static/
→ /var/www/careerbuddy4u/app/staticfiles/
```

Media files:

``` text
/media/
→ /var/www/careerbuddy4u/app/media/
```

Nginx also has an internal status endpoint bound to:

``` text
127.0.0.1:8080
```

and restricted to localhost.

### New application Nginx rule

Do not modify the existing CareerBuddy server block.

The new application should receive its own Nginx server block,
preferably using a new domain/subdomain, for example:

``` text
newapp.example.com
```

Nginx should reverse proxy to a **new, unused localhost port**.

The exact port must be selected after checking the final deployment
design.

------------------------------------------------------------------------

# 10. Network / listening ports

Observed listeners include:

     Port Listener/process            Existing purpose
  ------- --------------------------- ----------------------------------
       22 SSH / sshd                  Server administration
       80 Nginx                       HTTP
      443 Nginx                       HTTPS
     8000 Daphne                      Existing CareerBuddy application
     3306 MySQL                       Existing database
     6379 Redis                       Existing cache
     8080 Nginx                       Internal status endpoint
     3000 Grafana                     Monitoring
     3100 Loki                        Logging
     9090 Prometheus                  Monitoring
     9095 Loki                        Logging/API
     9100 Prometheus node exporter    Monitoring
     9104 MySQL exporter              Monitoring
     9113 Nginx Prometheus exporter   Monitoring
     9080 Promtail                    Log collection
    65529 Monarx agent                Security/agent service
    46373 Promtail                    Local/agent-related listener

### Important

The new application must not reuse:

``` text
8000
3306
6379
3000
3100
8080
9090
9095
9100
9104
9113
9080
```

A new localhost port should be selected only after confirming
availability at deployment time.

------------------------------------------------------------------------

# 11. Firewall

Ubuntu UFW is active.

Observed configuration:

``` text
Status: active
Logging: on (low)
Default: deny (incoming)
Default: allow (outgoing)
Default: disabled (routed)
```

Allowed incoming ports:

``` text
22/tcp
80/tcp
443/tcp
```

The same was observed for IPv6.

### Deployment implication

The new application should normally **not expose its application server
port publicly**.

Preferred architecture:

``` text
Internet
   ↓
Nginx :80/:443
   ↓
New application on 127.0.0.1:<new-port>
```

Do not add a public firewall rule for the new application port unless
there is a specific architectural reason.

------------------------------------------------------------------------

# 12. Monitoring infrastructure

The server has an existing monitoring/logging stack.

Observed services include:

``` text
grafana-server
prometheus
loki
promtail
nginx-prometheus-exporter
prometheus-mysql-exporter
prometheus-node-exporter
```

Grafana is listening on:

``` text
*:3000
```

Prometheus:

``` text
*:9090
```

Loki:

``` text
*:3100
*:9095
```

Prometheus node exporter:

``` text
*:9100
```

MySQL exporter:

``` text
*:9104
```

Nginx exporter:

``` text
*:9113
```

Promtail:

``` text
*:9080
```

Although some monitoring services listen on non-local addresses, UFW
currently allows only 22/80/443 inbound.

### New application requirement

Do not disable, remove, reconfigure, or restart the monitoring stack as
part of normal application deployment.

If monitoring integration is desired later, add it carefully without
breaking the existing monitoring system.

------------------------------------------------------------------------

# 13. Security-related services

Observed:

``` text
fail2ban.service
monarx-agent.service
```

Fail2ban is running.

Monarx security agent is running.

Do not disable or remove these services during deployment.

------------------------------------------------------------------------

# 14. `/var/www` structure

Observed:

``` text
/var/www/
├── careerbuddy4u/
│   ├── app/
│   └── html/
└── html/
```

Existing application:

``` text
/var/www/careerbuddy4u/app
```

Existing simple HTML directory:

``` text
/var/www/careerbuddy4u/html/index.html
```

Default web directory:

``` text
/var/www/html
```

### New application

Use a separate directory, for example:

``` text
/var/www/<new-application>
```

Do not place the new application inside:

``` text
/var/www/careerbuddy4u/app
```

------------------------------------------------------------------------

# 15. Linux users

Relevant accounts observed include:

``` text
root
www-data
mysql
redis
prometheus
grafana
```

The existing Django application runs as:

``` text
www-data
```

For the new application, a dedicated Linux user is recommended rather
than using `root`.

The exact user should be created only during the deployment phase.

------------------------------------------------------------------------

# 16. Docker

Docker is **not part of the planned deployment approach** for the new
application.

The new application should use a traditional Linux/Python deployment
unless later requirements explicitly justify another architecture.

------------------------------------------------------------------------

# 17. Cron

The root user's crontab was checked and returned:

``` text
no crontab for root
```

This does not rule out system-wide cron jobs or jobs belonging to other
users.

No cron changes are currently planned.

------------------------------------------------------------------------

# 18. Backups / snapshots

The Hostinger VPS dashboard showed:

``` text
Snapshots & backups: 4
```

A backup/snapshot should be verified before making significant
production changes.

Do not assume that the existence of four backups means the desired
recovery point is usable; verify backup status/recency in Hostinger
before deployment.

------------------------------------------------------------------------

# 19. Existing production architecture summary

``` text
                         INTERNET
                            |
                         Nginx
                     :80 / :443
                            |
              +-------------+-------------+
              |                           |
      careerbuddy4u.com                Grafana
              |                           |
              v                         :3000
       127.0.0.1:8000
              |
           Daphne
              |
           Django
              |
     /var/www/careerbuddy4u/app
              |
       +------+------+
       |             |
     MySQL         Redis
     :3306         :6379
       |             |
business_english_lms local-only
```

------------------------------------------------------------------------

# 20. Target architecture for the new application

The preferred target architecture is:

``` text
                         INTERNET
                            |
                         Nginx
                       :80 / :443
                            |
                     newapp.example.com
                            |
                            v
                  127.0.0.1:<NEW_PORT>
                            |
                   New application server
                  (Gunicorn/Uvicorn/etc.)
                            |
                    New application
                            |
                +-----------+-----------+
                |                       |
           PostgreSQL             Optional Redis
         NEW database             NEW/isolated
```

The exact application server (Gunicorn, Uvicorn, Daphne, etc.) must be
determined from the new application's code/framework.

------------------------------------------------------------------------

# 21. Resource considerations for the new application

Current server capacity observed:

``` text
4 vCPU
~15 GiB RAM
~185 GB free disk
0 swap
```

The existing application and monitoring stack are already running.

Before deployment, assess:

-   Expected PostgreSQL RAM usage
-   Application worker count
-   Background workers
-   Celery/queues if applicable
-   File/media storage requirements
-   Expected traffic
-   Database size
-   Logging volume
-   Monitoring overhead

Do not blindly configure a large number of application workers.

Because swap is currently absent, memory-heavy deployment configurations
should be avoided unless the memory strategy is deliberately reviewed.

------------------------------------------------------------------------

# 22. Known facts vs. things still to determine

## Confirmed

-   Hostinger KVM 4
-   Ubuntu 24.04.4 LTS
-   4 vCPU
-   \~15 GiB RAM
-   \~185 GB free disk at inspection
-   No swap
-   Nginx
-   Supervisor 4.2.5
-   Existing Django application
-   Existing Daphne service
-   Existing MySQL
-   Existing Redis
-   Existing monitoring stack
-   Existing CareerBuddy domain
-   Existing Nginx configuration
-   Existing Supervisor configuration
-   Existing Git repository
-   UFW active with 22/80/443 allowed
-   PostgreSQL service not installed
-   New application should use PostgreSQL
-   Docker is not desired for the new application

## Determine later during new application deployment

-   New application's exact framework/runtime
-   Required Python version
-   Required system packages
-   Application server choice
-   New application port
-   New domain/subdomain
-   PostgreSQL version
-   PostgreSQL database name
-   PostgreSQL database user
-   PostgreSQL authentication method
-   New application's process manager configuration
-   New Nginx server block
-   SSL certificate setup for the new domain
-   Background worker requirements
-   Whether the new application needs Redis
-   Backup strategy for the new database
-   Monitoring integration
-   Production environment variables

------------------------------------------------------------------------

# 23. Rules for an AI/developer assisting with deployment

When using this document to plan deployment:

1.  **Do not modify the existing CareerBuddy application.**
2.  **Do not use `/var/www/careerbuddy4u/app` for the new application.**
3.  **Do not use port 8000 for the new application.**
4.  **Do not use the existing MySQL database.**
5.  **Do not use the existing Redis database without explicit
    isolation/design.**
6.  **Do not modify the existing Supervisor program.**
7.  **Do not replace the existing Nginx configuration.**
8.  **Add a separate Nginx configuration for the new application.**
9.  **Keep the new application's application server bound to localhost
    unless there is a specific reason not to.**
10. **Do not expose a new application port through UFW unless
    necessary.**
11. **Use a dedicated application directory.**
12. **Use a dedicated Python virtual environment.**
13. **Use a dedicated Linux user where practical.**
14. **Use PostgreSQL for the new application.**
15. **Create a separate PostgreSQL database and user.**
16. **Do not expose secrets in deployment documentation or chat.**
17. **Do not restart existing production services merely to deploy the
    new application.**
18. **Do not run destructive cleanup commands such as `rm`,
    `docker system prune`, database drops, etc.**
19. **Before significant production changes, verify a usable Hostinger
    backup/snapshot.**
20. **Test the new application independently before changing DNS.**
21. **If a proposed change could affect the existing application, stop
    and explain the risk before executing it.**

------------------------------------------------------------------------

# 24. Recommended deployment philosophy

The safest approach is:

``` text
AUDIT
  ↓
BACKUP / VERIFY RECOVERY
  ↓
REVIEW NEW APPLICATION
  ↓
DESIGN ISOLATED DEPLOYMENT
  ↓
CREATE NEW USER/DIRECTORY
  ↓
INSTALL ONLY REQUIRED SYSTEM SOFTWARE
  ↓
CREATE POSTGRESQL DATABASE + USER
  ↓
CREATE NEW PYTHON VENV
  ↓
DEPLOY APPLICATION
  ↓
RUN APPLICATION ON UNUSED LOCAL PORT
  ↓
TEST LOCALLY
  ↓
ADD SEPARATE NGINX CONFIG
  ↓
TEST NGINX
  ↓
CONFIGURE HTTPS
  ↓
TEST NEW DOMAIN
  ↓
ONLY THEN CHANGE DNS IF REQUIRED
```

**Never start by changing the existing production Nginx/Supervisor/MySQL
configuration.**

------------------------------------------------------------------------

## Final safety summary

The most important existing production boundary is:

``` text
/var/www/careerbuddy4u/app
        |
        +-- Django
        +-- .venv
        +-- .env
        +-- MySQL: business_english_lms
        +-- Redis
        +-- Daphne: 127.0.0.1:8000
        +-- Supervisor
        +-- Nginx
```

Treat that entire stack as **existing production infrastructure**.

The new application should be built beside it, not inside it.

------------------------------------------------------------------------

# 25. Royal HRMS — DEPLOYED (2026-09-01)

The new application described in sections 20-24 has been deployed.
Everything below is **live production state**, not a plan. Treat this
section's resources with the same "do not touch without a reason" care
given to CareerBuddy's in section 1 — this is now a second real
production app on this VPS, just isolated from the first.

## Isolation summary

-   Application directory: `/var/www/royalhrms/app` (single git
    checkout containing both `backend/` and `frontend/`)
-   Git: `git@github.com:Sriainfotech/Royal-HRMS.git`, branch
    `production` (a stripped-down branch — only `backend/`,
    `frontend/`, `.gitignore`; no docs/CI/editor config). `demo` is
    the full development branch in the same repo.
-   Linux user: `royalhrms` (uid/gid 1000), home `/home/royalhrms`,
    holds the GitHub deploy key (`~/.ssh/id_ed25519`, read-only,
    scoped to this one repo)
-   Python: 3.12.3, venv at `/var/www/royalhrms/app/backend/.venv`
-   Node: 20.20.2 (system-wide via NodeSource, shared across the box —
    no other app currently needs Node)
-   PostgreSQL: database `royalhrms_db`, user `royalhrms_user`
    (password in `backend/.env`'s `DATABASE_URL` only — not recorded
    here). Multi-tenant via `django-tenants` (schema-per-company);
    `migrate_schemas --shared` has been run. No company/tenant schema
    exists yet as of this writing.
-   Redis: same shared instance as CareerBuddy (`127.0.0.1:6379`), but
    **logical DB index 2** (`redis://127.0.0.1:6379/2`) — used for
    Django cache/throttling, Channels layer, and Celery
    broker/result-backend all together. CareerBuddy's Redis usage is
    unaffected (different DB index).
-   Backend `.env`: `/var/www/royalhrms/app/backend/.env`
    (`chmod 600`, owned by `royalhrms`) — same exclusion rule as
    section 6: not reproduced here.

## Processes (Supervisor)

Config file: `/etc/supervisor/conf.d/royalhrms.conf` (separate from
`careerbuddy.conf`, never edit that file for this app).

| Program                    | Command                                                              | Port/role                     |
|-----------------------------|-----------------------------------------------------------------------|--------------------------------|
| `royalhrms_backend`         | `.venv/bin/daphne -b 127.0.0.1 -p 8001 config.asgi:application`      | Django/DRF + Channels, ASGI    |
| `royalhrms_frontend`        | `node_modules/.bin/next start -H 127.0.0.1 -p 3001`                  | Next.js 16 / React 19          |
| `royalhrms_celery_worker`   | `.venv/bin/celery -A config worker -l info --concurrency=2`          | background tasks               |
| `royalhrms_celery_beat`     | `.venv/bin/celery -A config beat -l info`                            | periodic tasks (see below)     |

All run as user `royalhrms`. Logs: `/var/log/royalhrms/*.{out,err}.log`
(separate from CareerBuddy's `/var/log/careerbuddy_daphne.*.log`).
Django's own app-level logs (auth, etc.) are separately written to
`backend/logs/` by the app itself.

Celery has real periodic tasks registered (`CELERY_BEAT_SCHEDULE` in
`settings.py`): missing-clockout checks and stale-provisioning sweep
every 5 min, daily absence-alert and birthday-wish jobs. Company
creation via the platform-admin UI runs as an async Celery task
(`apps.tenants.tasks.finish_provisioning_task`) — **the worker must be
running for company provisioning to complete**, it will otherwise sit
at `provisioning_status='pending'` indefinitely.

Reserved ports 8001/3001 should be added to the "must not reuse" list
in section 10 for any future third application on this box.

## Nginx

Two new files, both `careerbuddy4u`'s config untouched:

-   `/etc/nginx/sites-available/royalhrms-api` →
    `server_name api.royalhrms.com`, proxies to `127.0.0.1:8001`,
    serves `/static/` (Django admin CSS/JS only — media uploads go to
    Cloudinary, not local disk) from
    `/var/www/royalhrms/app/backend/staticfiles/`
-   `/etc/nginx/sites-available/royalhrms-frontend` →
    `server_name royalhrms.com www.royalhrms.com`, proxies to
    `127.0.0.1:3001`, serves `/_next/static/` directly from the build
    output

Both are symlinked into `sites-enabled` and were modified in place by
`certbot --nginx` to add the HTTPS server blocks and HTTP→HTTPS
redirect.

**Important app-specific setting:** Django's `SECURE_PROXY_SSL_HEADER`
is set to trust `X-Forwarded-Proto`, and `SECURE_SSL_REDIRECT=True` is
on for non-DEBUG. If either of these two new Nginx configs is ever
rewritten from scratch, `proxy_set_header X-Forwarded-Proto $scheme;`
**must** be preserved on both, or the backend will infinite-redirect
every HTTPS request.

**Important app-specific setting #2 — proxy buffer sizes.** Both
`location /` blocks (in `royalhrms-api` and `royalhrms-frontend`) carry:
```
proxy_buffer_size 16k;
proxy_buffers 4 16k;
proxy_busy_buffers_size 16k;
```
Without these, Nginx's default header buffer is too small for a
**successful** login response — Django/simplejwt sets multiple
`Set-Cookie` headers (access + refresh JWTs) that exceed the default
(~4-8k), and Nginx returns `502 Bad Gateway` with
`upstream sent too big header while reading response header from
upstream` in `/var/log/nginx/error.log`, even though the backend
itself responded fine. This bit both hops: first `royalhrms-api`
reading Daphne's response, then — because the frontend's own
`next.config.ts` rewrite calls `api.royalhrms.com` server-side and
relays the same cookies back through its own response —
`royalhrms-frontend` reading the Next.js response too. **Both** files
need the fix, not just one. If either config is ever rewritten from
scratch, re-add these three lines to its `location /` block, or logins
will silently 502 while every other page load works fine (the failure
only shows up on a request that actually sets auth cookies, so it's
easy to miss in a quick smoke test).

## HTTPS / DNS

-   Domains: `royalhrms.com`, `www.royalhrms.com` (frontend),
    `api.royalhrms.com` (backend) — all A records → `2.25.73.246`
-   Certificate: Let's Encrypt via `certbot --nginx`, covers all three
    names in one cert, registered to `sriainfotech@gmail.com`,
    auto-renewal already scheduled by certbot (separate from whatever
    renews CareerBuddy's cert)

## Known gaps (deliberately deferred, not forgotten)

-   **Cloudinary is unconfigured** — `CLOUDINARY_CLOUD_NAME` /
    `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` are blank in
    `.env`. The app boots fine (django-environ only errors on a
    *missing* key, not an empty one), but any file upload (profile
    photos, documents, face-recognition images) will fail until real
    credentials are added and `royalhrms_backend` is restarted.
-   `SARVAM_API_KEY` is blank — voice-command features stay disabled
    (fails soft by design, does not block anything else).
-   **Per-tenant email is a genuinely separate setting per company** —
    each company has its own `Settings → SMTP` (backed by
    `apps.accounts.models.SMTPSettings`, one row *inside that company's
    own schema*), used for that company's own OTP/notification emails.
    A brand-new company has none configured yet, so its users will hit
    `RuntimeError: No active SMTP configuration found` on any
    OTP-driven flow (login OTP, forgot-password) until someone
    configures it from inside that company's own dashboard. This is
    expected per-company onboarding, not a deployment bug — don't
    confuse it with the *platform-level* `PlatformSMTPSettings` below.

## Resolved during initial shakedown (2026-09-03) — kept for reference

-   ~~"Production email is not actually wired" (EMAIL_HOST/PORT/USER/
    PASSWORD unused)~~ — **this was a wrong finding, corrected after
    investigation.** Every real email path in this codebase
    (`apps.tenants.utils._get_platform_smtp_connection` for
    platform-level mail, `apps.accounts.utils._get_smtp_connection` for
    per-tenant mail) builds its own explicit SMTP connection from a
    database-stored settings row — neither ever touches Django's global
    `EMAIL_HOST`/`send_mail()`. No settings.py fix was needed or applied.
-   **Company-provisioning welcome email can silently not send** — it's
    deliberately best-effort (a bad platform SMTP config must never
    block company creation), so a misconfigured/unconfigured
    `PlatformSMTPSettings` fails silently with only a log line, not a
    visible error anywhere in the UI. Added `POST
    /api/platform-admin/smtp-settings/test/` + a "Send test email"
    button on the Email Settings page specifically so this can be
    verified without waiting on a real company to be created — pushed
    to `production`/`demo`, see `apps/tenants/views.py`
    `PlatformSMTPTestEmailView`.
-   **Reveal-password modal disappeared instantly** — `CompaniesTable`'s
    own refetch after a successful reveal flipped the parent page back
    into its "loading" branch, which unmounted the whole table
    (destroying the modal holding the one-time password) before an
    admin could read/copy it. Fixed in `companies/page.tsx` — the
    full-page spinner now only shows on the very first load
    (`loading && !companyList`), not on every background refetch.
-   **Login 502'd through Nginx (but only on success)** — see the
    "proxy buffer sizes" note under Nginx above. Cost real time to
    diagnose because every synthetic test (curl with an empty/invalid
    body) got back a small, cookie-free error response and looked
    fine — the bug only manifests on a response that actually sets the
    JWT auth cookies. Worth remembering for the *next* app deployed
    this way: **always smoke-test with a real successful login**, not
    just "does the server respond."
-   A `PlatformAdmin` account and a first company (`DEMO2026`) now
    exist — platform-admin login and one company's login are both
    confirmed working end-to-end as of this entry.
