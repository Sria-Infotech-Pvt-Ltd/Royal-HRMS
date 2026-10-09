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

------------------------------------------------------------------------

# 26. Application change log (production support, 2026-09-30 → 2026-10-03)

This section covers **application-level** feature/bug-fix work on top of
the already-deployed stack described above — not infrastructure. It's the
recent slice of an ongoing, longer production-support engagement; only the
work actually carried out in this stretch is logged here, in the order it
happened. Every change listed was validated locally first (isolated Docker
Postgres test DB, project-local venv, real `manage.py test` runs — never
against the production database) before being committed. As of this
entry, everything below is **committed to `production` on GitHub**
(`Sriainfotech/Royal-HRMS`) but — see the Git/deploy-key note at the end of
this section — **not yet pulled onto this server**, pending a deploy-key
fix.

## Asset Management

-   Fixed a real production 404 in "Assign Asset": the frontend was
    passing an employee's human-readable code into a backend route typed
    `<uuid:employee_id>`. One-line frontend fix.
-   Added Asset Category / Asset Type master data (mirrors
    Department/Designation: cascading dropdowns, "Other" category/type
    with free-text capture, quick-add modals). New models
    `AssetCategory`/`AssetType`, migrations `0003`/`0004` (the latter
    seeds default categories/types per tenant schema — confirmed safe via
    this VPS's own Postgres: `apps.assets` is a `TENANT_APP`, so this runs
    once per company schema, not once globally).
-   Added a Send-to-Maintenance / Complete-Maintenance lifecycle:
    `AssetMaintenanceRecord` model + migration `0005`, new views/
    serializers, `active_maintenance` field on the asset serializer,
    frontend action buttons. Kept as a separate history table from
    `AssetAssignment` (an asset can cycle through assign/return and
    repair/complete independently) — verified with an end-to-end test
    that assignment history is never touched by a maintenance cycle.
-   **Production incident during this work:** the three migrations above
    were pulled to this server (code) before `migrate_schemas` had been
    run, so `AssetCategory`/`AssetType` tables didn't exist yet — any
    request touching Asset Category hit `relation "assets_category" does
    not exist`. Fixed by running `.venv/bin/python manage.py
    migrate_schemas` on the server (applies to every tenant schema) —
    confirmed via `showmigrations assets` before and after. No data was
    lost; this was a missing-migration-step issue, not a bad migration.

## Employee Details — field-level editability and protection

Employee ID and Employee Name are now **permanently immutable** through
`EmployeeDetailView.put()` (`backend/apps/accounts/views.py`), regardless
of onboarding status — previously only a front-end convention with no
backend enforcement, and Employee Name was only locked *after* onboarding
completed, not always. A direct API call can no longer change either
field. Also closed the one remaining gap: Django Admin's `UserAdmin` now
has `employee_id`/`full_name` in `readonly_fields` too.

Made genuinely editable (previously either locked or never wired up at
all), for any role already holding `employees.edit` (System Admin, HR
Admin, Branch Admin — same existing branch-scope rules apply, nothing new
introduced):

-   **Date of Birth** — now validates past-date + age 18–80 by calling the
    same validator the onboarding wizard already used
    (`EmployeeProfileSerializer.validate_date_of_birth`), instead of only
    checking date format as before.
-   **Mobile Number** — no longer locked once onboarding completes; now
    validated with the same phone regex used elsewhere
    (`_PHONE_RE_PROFILE`) instead of no format validation at all.
-   **Email** — new capability. Validates format + uniqueness, and reuses
    an existing-but-orphaned helper, `send_email_change_notifications()`
    (`apps/accounts/utils.py`) — sends a confirmation to the new address
    and a security alert to the old one. (Found in passing: a dedicated
    `EmployeeChangeLoginEmailView` is referenced in a docstring elsewhere
    in the codebase but doesn't actually exist — likely removed at some
    point; this fix did not recreate it, just reused the still-working
    notification helper directly in the existing PUT endpoint instead.)
-   **Date of Joining** — no longer locked once onboarding completes,
    same pattern as Mobile Number above.

Frontend: the Employee Details edit form (`frontend/app/dashboard/
employees/_data.ts`, `[id]/page.tsx`) was updated field-by-field to match
— Login Email and Phone switched from `readonly` to real inputs, Date of
Joining likewise, both added to the save payload (previously silently
omitted even though the UI showed them).

## Employee ID format change

Replaced the previous pure-sequential format (`EMP00001`, `EMP00002`, …)
with `PREFIX + date-of-joining(DDMM) + name-initials` (e.g. a company with
prefix `RSS`, employee "Teerdaveni Gedela" joining 3 Aug → `RSS0308TG`) —
`backend/apps/accounts/models.py`, `EmployeeCodeSettings.generate_employee_id()`.

-   **Existing employee IDs are completely untouched** — this only
    affects IDs generated for employees created *after* this change.
-   Collision handling: two people with the same join-date+initials get a
    numeric suffix (`RSS0308RK`, `RSS0308RK2`, …), resolved inside the
    same database lock the old sequence counter used, so two concurrent
    signups can't collide.
-   Single-word names fall back to repeating the one initial twice
    (`"Madonna"` → `MM`) rather than inventing a placeholder character.
-   All three places that generate an employee ID (direct creation,
    onboarding-candidate approval, bulk import) already shared one
    function, so this needed no per-call-site changes.
-   The Employee ID Settings page (`frontend/app/dashboard/settings/
    employee-code/page.tsx`) had its now-meaningless "Digit padding" /
    "Next sequence number" inputs removed from the visible form (the
    backend fields themselves were left alone — still part of the saved
    settings object, just not shown as editable, so the API contract
    didn't change) and the preview rewritten to show the new format with
    example data.
-   Added a **read-only preview tool** (new management command,
    `dry_run_employee_id_conversion`) that computes what every *existing*
    employee's ID *would* look like under the new format, with full
    collision detection — makes zero database writes. This exists purely
    so the old→new mapping can be reviewed before anyone decides whether
    to actually convert existing employees' IDs (that conversion itself
    was explicitly **not** implemented — only investigated and judged
    higher-risk than it's worth, mainly because of dead
    bookmarks/shared links built on the old IDs).

## Leave Type name now editable

Settings → Leave Policy → editing an existing leave type now shows and
lets you change its display name (previously read-only in the Edit modal,
even though the name was editable at creation time) —
`LeavePolicyUpdateSerializer` (`backend/apps/hrms/serializers.py`) gained
a validated `leave_type_label` field, reusing the exact same
character-rule/duplicate-name check the Create flow already used (factored
into one shared `_validate_leave_type_label()` function so the two flows
can't drift apart). The leave type's internal key/slug never changes —
only the display label.

## "Menstrual Leave not showing in Employee Profile" — real root cause

Not a bug in saving, displaying, or caching the policy — all of those
work correctly. The actual gap: an employee's visible leave balances are
driven entirely by `LeaveBalance` rows, which were previously only ever
created (a) when an employee is created, or (b) by the annual Celery
reset (`apps/hrms/tasks.py: reset_annual_leave_balances`). **Adding a new
leave type (e.g. a custom "Menstrual Leave" policy) mid-year never
granted existing employees a balance for it** — nothing re-evaluated
already-existing employees against a brand-new policy; they'd have had to
wait for the next annual reset. (This exact category of gap has bitten
this codebase once before — see migration
`0019_backfill_missing_leave_balances.py`'s own docstring, which patched
a related but different trigger.)

Fixed by adding `_allocate_new_policy_for_existing_employees()`
(`backend/apps/hrms/views/leave.py`), called once, synchronously, right
after a new `LeavePolicy` is created — reuses the existing eligibility
logic (branch/department/designation/minimum-service-period via
`_eligible_for_policy()`, gender via the same single-line check the
employee-creation allocator already used) rather than a second
implementation. Idempotent (`get_or_create`, safe to re-run), and
deliberately not wrapped in one giant transaction so a partial failure
can be retried without re-processing already-done employees. Kept
synchronous (no new Celery task) — creating a leave policy is a rare,
admin-initiated action, not a hot path, and the realistic employee counts
here don't warrant the added complexity.

**Found but not fixed (pre-existing, separate issue):** a custom leave
type's display name can be up to 100 characters, but the column that
actually stores a leave type key on `LeaveBalance`/`LeaveRequest` is
capped at 20 — a long enough custom name (e.g. "Engineering Only Leave")
would crash *any* balance-crediting path with a database error, not just
the new backfill function. Worth its own fix later; out of scope for the
Menstrual Leave issue itself.

## "Managers do not have a reporting manager" blocking unrelated edits

Regression affecting every Manager-role employee: saving *any* field
change on their Employee Details page (even just Date of Birth) failed
with this error. Root cause: `EmployeeDetailView.put()` rejected the
request just because the `reporting_manager_id` key was *present* in the
payload (which it always is — the frontend sends the full form every
save, the same way every other field on that page works), regardless of
whether its value had actually changed. Fixed by moving the role check to
only fire when an actual (non-empty) value is being assigned — mirrors
the equivalent, already-correct check in the employee-creation endpoint.
Managers still cannot be assigned a reporting manager; only the false
rejection on unrelated edits is gone.

## Punch-in taking 2–3 minutes / multiple clicks not helping

Investigated the full Clock In/Out chain (GPS acquisition → geofence
pre-check API call → face-capture modal → punch API call). Confirmed the
backend has no slow external calls anywhere in this path (geofencing is
local Haversine math, face matching is a local embedding-distance
comparison — no third-party API). The concrete, fixed bug:
`ClockInButton.tsx`'s busy/disabled state didn't include the `isLocating`
flag from `useClockWidget`, so the button stayed clickable while GPS +
the geofence pre-check were still running — a repeated click started a
second, fully independent punch flow stacked on top of the first, which
explains "even trying multiple times" making it worse, not better.
One-line fix: `isBusy` now includes `isLocating`. (A secondary,
unconfirmed suspect also noted for later: a synchronous Redis/WebSocket
push sits in the response path after the punch is saved — not touched,
since it needs real production timing data to confirm before acting on
it.)

## Branch Admin "Clock In/Out not showing" — investigated, no code change

Traced the dashboard-resolution logic (`frontend/app/dashboard/page.tsx`)
and confirmed Branch Admin is seeded with `employees.view` and therefore
*should* land on the same `HRDashboard` (and its already-present
`ClockInButton`, inside `HrConsole`) that HR Admin uses — there is no
code path that excludes Branch Admin specifically, and the backend punch
API has no role restriction at all (`IsAuthenticated` only). Likely
explanation for the specific report: the frontend session cookie
(`role`/`permissions`/`can_manage_team`) is set once at login and never
refreshed mid-session — confirmed by tracing every call site of
`saveAuth()` — so an account whose permissions changed or were only
recently granted could be showing a stale dashboard bucket until they log
out and back in. No code was changed for this one; recommended next step
was simply "log out and back in," with a DB-side permission check as the
fallback if that doesn't resolve it.

## Employment Type — investigated only, not implemented

Confirmed "Employee Type" already exists as a UI dropdown in two
employee-creation flows (`AddEmployeeModal.tsx`, `employees/new/
page.tsx`, both offering Permanent/Contract/Intern/Probation) but is
**silently discarded** in both — one flow sends it and the backend never
reads it, the other never sends it at all despite showing it on a review
screen. No `employment_type` field exists anywhere on `User`/
`EmployeeProfile` today. A real field + migration would be needed to
implement this properly; deliberately not done yet, pending a decision on
scope (this was purely an inspection pass).

## Git / deploy-key issue found during this session (unresolved as of this entry)

While trying to deploy the above to this server, `git pull origin
production` started failing with `ERROR: Repository not found`. Traced to:
this server's SSH deploy key (`~/.ssh/id_ed25519`,
`royalhrms-deploy@srv1795199`) authenticates successfully against GitHub,
but is scoped to a *different* repository
(`Sria-Infotech-Pvt-Ltd/Royal-HRMS`) than the one actually in use
(`Sriainfotech/Royal-HRMS` — confirmed as the real one since local
development has used that name throughout). The remote URL on this server
has been corrected back to `git@github.com:Sriainfotech/Royal-HRMS.git`,
but **the deploy key itself still needs to be added to that repo's
Deploy Keys list** (`github.com/Sriainfotech/Royal-HRMS/settings/keys`,
read-only, no write access needed) before `git pull` will work again.
Public key, for whoever does this:
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAICtAGEq4cTLoKEycfWO6O5rsTuCysVO3IQosEEJAR+W3 royalhrms-deploy@srv1795199
```
**As of this entry, the application code above is committed to GitHub but
has not yet been pulled onto this server** — update this note once the
deploy key is added and the pull/build/restart has actually happened.

------------------------------------------------------------------------

# 27. Application change log (production support, 2026-10-07 → 2026-10-08)

Continuation of section 26's ongoing production-support engagement. Every
change below was implemented and test-validated locally first (the same
isolated local Postgres test setup as before — a Docker container on
`localhost:15432`, never the production/Neon-style database) before being
committed. **Deployment status is called out explicitly per item below —
several of these commits are confirmed pushed to GitHub but this document
does not have confirmation that `migrate_schemas` + service restart were
actually run on this server for every one of them.** Treat any item marked
"restart/migration not confirmed" as needing a fresh `showmigrations`
check on the server before assuming it's live.

## Leave request detail — owner-with-approve-permission wrongly blocked

A manager/COO who also holds `leave.approve` got "Permission denied"
re-opening their **own** submitted leave request once it moved past their
own approval to L2/HR. Root cause: `LeaveRequestDetailView._get_request()`
(`backend/apps/hrms/views/leave.py`) only exempted the request owner from
its *first* rejection branch (no-`leave.approve` case); an owner who also
holds `leave.approve` fell into the second branch, which runs
`_can_hr_access_request()` — a check with no reason to recognize someone as
their own l1/l2 approver, since the request is theirs, not one they're
reviewing for someone else. Fixed by making the owner check short-circuit
unconditionally, before either branch. Regression test added. Committed
`0b1af51`. No migration.

## Employee-wise shift timing (SGT/ICT, UK, global default)

New requirement: two additional named shifts — **SGT/ICT 07:30–16:30** and
**UK 12:00–21:00** — assignable per employee, while every employee with no
assignment keeps the existing global **09:00–18:00** fallback byte-for-byte
unchanged.

-   Reused the existing `WorkingHoursPolicy` model (already built, never
    wired in) as the shift catalog instead of creating a duplicate.
-   New `EmployeeShiftAssignment` model + migration `0044`, mirroring the
    established `EmployeeWeeklyOffAssignment` architecture exactly
    (date-ranged, history-preserving, partial-unique "one open assignment
    per employee" DB constraint).
-   New idempotent seed migration `0045` (creates the two named policy rows
    `WH-SGT-ICT`/`WH-UK` — skips if an admin already created a same-named
    row; never touches the existing global settings).
-   New `ShiftCacheService` resolver (`backend/core/cache_service.py`) —
    per-employee effective shift, falling back to the global singleton,
    mirroring `WeeklyOffCacheService`'s own priority-chain pattern.
-   Late-arrival/early-exit checks in `services_attendance.py` now resolve
    the employee's actual shift instead of always reading the global
    config.
-   **Highest-risk area, found and fixed via an independent adversarial
    review before shipping:** the missing-clockout Celery job
    (`services_unpunch.py`) originally computed one global deadline for
    the whole tenant — a UK-shift employee would've been falsely flagged
    "incomplete" around 18:00 while still legitimately working, and an
    SGT/ICT employee's real no-show wouldn't be caught until 18:10 instead
    of ~16:40. Rewritten to resolve each employee's own deadline in one
    bulk query (no N+1). A second, narrower bug (an earlier-review fix)
    was then also fixed: the job's early-exit optimization filtered
    `WorkingHoursPolicy.objects.filter(is_active=True)`, so deactivating a
    policy that was still actively assigned to someone could delay their
    detection — fixed by not filtering that specific floor-calculation
    query by `is_active` (the filter was only ever a cheap optimization
    gate, never the real per-employee decision, so widening it is strictly
    safer).
-   New HR UI: Attendance & Time → **Shift Assignment** tab (employee
    assignment list/bulk-assign/history) with an embedded **Shifts**
    management card (the orphaned `WorkingHoursPolicy` CRUD, wired into a
    UI for the first time) — `frontend/app/dashboard/attendance/
    _components/ShiftAssignmentTab.tsx` / `ShiftMasterCard.tsx`.
-   33 new backend tests (`tests_shift_assignment.py`).

## Daily Clock In/Out limit — exactly 1 IN + 1 OUT per day

New, explicitly confirmed business requirement, **not** a bug fix of the
prior design: the system previously allowed unlimited alternating
Clock-In/Clock-Out cycles per day by design (append-only punch log, no
cap) — this was intentionally replaced with a hard cap of one Clock In and
one Clock Out per employee per attendance day.

-   `PunchService._validate_daily_punch_limit()`
    (`services_attendance.py`) — rejects a 2nd Clock In or Clock Out with a
    specific message for each case ("already clocked in" vs "already
    completed your attendance for today").
-   Race-condition-safe by construction, not just by convention: the
    authoritative check runs inside a `transaction.atomic()` block holding
    `select_for_update()` on the employee's `AttendanceRecord` row for that
    date — safe even for the very first punch of the day because that
    model already has a real `unique_together=('employee','date')`
    constraint (Django's documented `get_or_create()`-under-a-unique-
    constraint retry behavior handles the race). Verified with actual
    concurrent `threading.Thread`s against a real Postgres connection (not
    just reasoned about) — 5 simultaneous Clock-In attempts → exactly 1
    success, 4 clean rejections, 1 punch row.
-   New `day_completed` field on the `/attendance/today/` response; both
    real Clock In/Out UI entry points (`ClockInButton.tsx`,
    `my-attendance/_components/ClockWidget.tsx`) now show "Attendance
    Completed" and disable themselves once both punches exist for the day,
    instead of reverting to a clickable "Clock In".
-   17 new backend tests (`tests_daily_punch_limit.py`).

Shift timing + daily punch limit were committed together: **`326aa01`**.
**Contains migrations `0044`/`0045` — pushed to GitHub and pulled onto this
server (confirmed via a pasted `git pull` transcript), but `migrate_schemas`
+ service restart on this server were not confirmed back in this session.
Run `showmigrations attendance` here before assuming `0044`/`0045` are
live.**

## UK Shift — geofence bypass with GPS still mandatory

Confirmed requirement: UK Shift employees (and only UK Shift employees,
identified by the **immutable** `WorkingHoursPolicy.policy_code='WH-UK'`,
never the editable display name) can clock in/out from anywhere — branch
geofence distance is not enforced for them — but GPS capture/storage stays
mandatory exactly as for everyone else, and HR/Admin can see the actual
captured coordinates.

-   New `_validate_uk_shift_bypass()` in `services_geofencing.py`, called
    from the existing `_validate_office()` path (UK employees stay on the
    normal "office" attendance mode on the frontend — critical, because
    GPS capture itself is only wired up for that mode; routing UK through
    a different mode like `field` would have silently disabled GPS capture
    entirely).
-   `ShiftCacheService._Shift` extended with a `policy_code` field
    (additive, trailing-default, doesn't break any existing caller) so the
    geofence layer can identify UK Shift without duplicating shift
    resolution.
-   HR attendance detail API/UI gained `clock_in/out_latitude/longitude` +
    a plain `maps.google.com/?q=` link (no maps SDK, no API key, no new
    dependency) — this was the first time raw coordinates were exposed to
    HR at all (previously only an inside/outside-geofence boolean + a
    distance figure).
-   13 new backend tests (`tests_uk_shift_geofence.py`).

Committed as **`94c489d`** ("uk shift geotagging"). No migration required
(reused existing `AttendancePunch` columns). **Server restart not
confirmed back in this session.**

## Human-readable punch location (reverse geocoding)

Requirement: show HR an actual place name ("Hyderabad, Telangana, India"),
not just raw coordinates — while never blocking Clock In/Out on a
third-party network call.

-   Confirmed via inspection (and the codebase's own prior documented
    admission, in `apps/hrms/models.py`'s `WorkFromHomeRequest` docstring)
    that this app had **no** geocoding integration of any kind before this.
-   New `AttendancePunch.location_label` field + migration `0047`
    (additive only).
-   New `services_geocoding.py` — OpenStreetMap Nominatim (free, no API
    key, no new pip dependency — reuses `requests`, already a project
    dependency). Pure function, catches every failure mode internally,
    never raises.
-   New `reverse_geocode_punch_task` Celery task, dispatched via
    `transaction.on_commit()` **only after** the punch is already
    committed — a geocoding failure/timeout/rate-limit can never turn a
    successful punch into a failed request (verified with a test that
    forces the mocked geocoder to raise mid-task and confirms the task's
    own outer exception handler still swallows it).
-   HR detail drawer shows the resolved label above the existing
    coordinates/map link, with a graceful "Location name unavailable"
    fallback — coordinates are never removed or replaced.
-   20 new backend tests (`tests_punch_location_geocoding.py`).

Committed by the team as **`a87bd1e`** ("human readable attendance
location"). **Contains migration `0047` — pushed, but `migrate_schemas` +
restart not confirmed back in this session.**

## UK office-vs-outside location label refinement

Follow-up clarification after the above shipped: when a UK Shift
employee's GPS places them genuinely inside their own branch's geofence,
show **"Office – <Branch Name>"** instead of unnecessarily reverse-
geocoding coordinates that are already known to be the office; when
they're actually elsewhere, show the real reverse-geocoded place name
exactly as before. The branch name must never be shown when the employee
is actually elsewhere.

-   `_validate_uk_shift_bypass()` now genuinely computes inside/outside
    status for UK Shift via a newly-extracted shared helper,
    `_match_branch_within_radius()` — the **exact same** Haversine-
    distance-vs-radius algorithm `_validate_office()` already uses for
    real enforcement elsewhere, so the two can never drift apart. The
    result is display-only: `is_allowed` stays unconditionally `True` for
    UK Shift regardless of the outcome.
-   `reverse_geocode_punch_task` now skips the Nominatim call entirely
    (zero HTTP calls) and sets the office label directly when (and only
    when) `is_inside_geofence is True` **and** the employee's shift for
    that punch's own date is `WH-UK`. Every other case — UK-outside,
    UK-with-no-branch-match, and **all** SGT/ICT/default-shift punches
    regardless of their own inside/outside status — falls through to the
    pre-existing unconditional reverse-geocode call, unchanged.
-   Found and fixed one now-superseded test (from the UK Shift geofence
    work above) that had encoded the old "always report not-evaluated"
    assumption — updated with an inline note explaining why, not silently
    changed.
-   13 new tests (`tests_uk_office_location_label.py`); combined regression
    run across all five shift/punch/geofence/location test files together:
    96/96 passing.

Committed as **`30ffd55`** (reused an earlier commit message, "human
readable attendance location" — the actual diff is the office-label
refinement described here, confirmed via `git show`). No migration
required. **Server restart not confirmed back in this session.**

## Unrelated work observed on `production` during this window

Two commits appeared on this branch from elsewhere during this engagement,
not part of the work above — noted here only because they're now part of
this server's deployment history:

-   `65ed18c` — "Speed up face clock-in: preload models, cache weights,
    faster capture"
-   `843f4d8` — "Reduce face clock-in retries: telemetry, live framing
    hints, robust liveness, fill light" (adds `FaceCaptureTelemetry`
    model/migration `0046`, a read-only `face_clockin_report` management
    command, and a `NEXT_PUBLIC_FACE_FLOW_V2=0` frontend kill switch —
    inspected on request and confirmed it does not touch the face-match
    threshold, the low-confidence margin, or the blink-AND-head-turn
    liveness requirement)
-   `1249dbe` — "Speed up face clock-in: preload+warm models at dashboard,
    camera first, screen/camera brightness ramp" — **note:** this touches
    `ClockInButton.tsx` and `my-attendance/_components/ClockWidget.tsx`,
    the same two files the Daily Clock In/Out Limit work above also
    modified (for the `day_completed`/"Attendance Completed" disabled
    state) — worth a manual smoke-test of that disabled state once this is
    live, since it hasn't been specifically re-verified after this other
    commit landed on top.

## Known pre-existing flaky test (not introduced by, or fixed during, this window)

`apps.attendance.tests_face_verification.FaceRegistrationMyStatusTests
.test_returns_latest_request_when_several_exist` is genuinely
nondeterministic — it creates two records back-to-back with no delay and
resolves "latest" via `order_by('-created_at')` with no tiebreaker.
Confirmed flaky by running it in isolation three times with zero code
changes (fail/pass/pass) and by diffing full-suite failure lists against
the unmodified base commit (identical failure set either way). Left
untouched per this engagement's "don't modify unrelated failing tests"
rule — flagging it here so it isn't mistaken for a regression from any of
the work above.

## Outstanding action item for whoever deploys this batch

Run on the server, in this order, before assuming any of the above is
live:
```
cd /var/www/royalhrms/app/backend
git log --oneline -8                          # confirm HEAD matches 30ffd55
.venv/bin/python manage.py showmigrations attendance   # confirm 0044/0045/0047 applied
.venv/bin/python manage.py migrate_schemas             # if any are unapplied
sudo supervisorctl restart royalhrms_backend royalhrms_celery_worker royalhrms_celery_beat
sudo supervisorctl status royalhrms_backend royalhrms_celery_worker royalhrms_celery_beat
```
The Celery worker specifically must be running for the reverse-geocoding
task (human-readable location) to ever populate `location_label` — a
restarted backend alone is not sufficient for that one feature.
