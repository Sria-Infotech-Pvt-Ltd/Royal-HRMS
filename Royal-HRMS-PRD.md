# Royal HRMS — Product Requirements Document

**Product:** Royal HRMS  
**Client:** Royal Staffing Services LLP  
**Version:** 1.0  
**Status:** Approved — Green Signal  
**Last Updated:** June 2025  
**Classification:** Confidential

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Criteria](#3-goals--success-criteria)
4. [User Roles](#4-user-roles)
5. [User Flows](#5-user-flows)
6. [Feature Requirements](#6-feature-requirements)
7. [Non-Functional Requirements](#7-non-functional-requirements)
8. [Security Requirements](#8-security-requirements)
9. [Integration Requirements](#9-integration-requirements)
10. [Out of Scope — V1](#10-out-of-scope--v1)
11. [Constraints & Assumptions](#11-constraints--assumptions)
12. [Glossary](#12-glossary)

---

## 1. Product Overview

Royal HRMS is a multi-role enterprise Human Resource Management System for Royal Staffing Services LLP. It covers the complete employee lifecycle — from candidate sourcing through recruitment, onboarding, day-to-day HR operations, and eventual separation.

The system is a web application with a responsive interface that works across desktop, tablet, and mobile. Five distinct user experiences are delivered from a single platform, each tailored to a specific role.

The company operates across four branches:

- Bengaluru HQ
- Mumbai
- Chennai
- Delhi

All branches share a single system. Data visibility and actions are scoped per role and per branch where applicable.

---

## 2. Problem Statement

Royal Staffing Services LLP currently manages HR operations through spreadsheets and manual processes. This creates the following problems:

- Recruitment tracking is manual — no centralised pipeline, status updates happen over email
- Employee records are scattered across files — no single source of truth
- Leave approvals happen verbally or via chat — no audit trail
- Payslip generation is manual — error-prone and time-consuming every month
- Employees have no self-service access — every request requires HR intervention
- Attendance is tracked manually — no automated clock-in, no monthly summaries
- Multi-branch visibility does not exist — each branch operates in a silo
- There is no referral program — informal referrals have no tracking or bonus system

---

## 3. Goals & Success Criteria

### Primary Goals

- Replace all manual spreadsheet-based HR processes with a unified digital platform
- Give every employee self-service access to their own HR data
- Provide HR with a complete recruitment-to-retirement workflow in one place
- Enable multi-branch management and data visibility for admin and HR
- Ensure all data is auditable — every action is traceable to a user

### Success Criteria

| Metric | Target |
|--------|--------|
| All 15 modules functional and tested | 100% coverage |
| All 5 role experiences working end-to-end | No broken flows |
| Responsive at 480px, 768px, 900px, 1280px | All breakpoints pass QA |
| API response time | P95 < 500ms |
| First contentful paint | < 1.5 seconds |
| Security | OWASP Top 10 addressed |
| Uptime | 99.5% SLA |

---

## 4. User Roles

The system has five distinct roles. Each role gets a tailored navigation, dashboard, and feature set. All permissions are enforced server-side.

### HR Admin

The primary operator of the system. Has full access to all modules.

**Responsibilities:**
- Manage the full recruitment pipeline — add candidates, schedule interviews, mark selected/rejected, send emails, approve onboarding
- Maintain employee records — create, edit, deactivate employees
- Configure and run payroll — set salary structures, generate payslips, export reports
- Manage leave policy — configure leave types, approve requests
- Approve expense claims
- Post announcements and upload company documents
- Manage the referral program — approve bonuses
- Process separations and FnF settlements
- Configure all system settings — email templates, SMTP, attendance rules, etc.

### System Admin

Platform-level access. Manages the infrastructure of the HRMS, not individual employee data.

**Responsibilities:**
- Manage branches — add, edit, view employee distribution per branch
- Manage user accounts and role assignments
- Configure roles and permissions
- Monitor system health — active sessions, module activity, storage usage
- View and export audit logs
- Configure SMTP and notification settings
- Manage company-level settings

### Manager

Team-scoped access. Can see and act on their direct reports only.

**Responsibilities:**
- Approve or reject leave requests from team members
- Approve or reject expense claims from team members
- Approve face enrollments for new team members
- View team attendance and live status
- Schedule and manage interviews
- Submit and track referrals
- Access own HR self-service (payslip, leave, attendance, expenses)

### Employee

Self-service access. Can only see and act on their own data.

**Responsibilities:**
- Clock in and clock out
- Complete face enrollment on hire (one-time)
- View own attendance history and monthly summary
- Apply for leave
- View own leave balance
- View own payslips
- Submit expense claims
- Submit referrals
- View company announcements and documents
- Track own request statuses
- Initiate separation (resignation)

### Candidate

Pre-employment portal access only. A temporary role that converts to Employee on HR approval.

**Responsibilities:**
- Complete the onboarding wizard (personal details, address, education, documents, bank, review)
- View application and approval status
- Proceed to employee dashboard after HR approves

---

## 5. User Flows

### 5.1 Authentication Flow

```
User visits /login
  │
  ├── Enters email + password
  │     ├── Invalid credentials → error message, increment failed attempt counter
  │     ├── Account locked (5 failed attempts) → locked message with time remaining
  │     └── Valid → JWT access token (15 min) + refresh token (7 days) issued
  │
  ├── First login (must_change_password = true)
  │     └── Redirect to /change-password before any other page
  │
  └── Successful login → redirect to role-specific dashboard
        ├── HR Admin → /dashboard/hr
        ├── System Admin → /dashboard/admin
        ├── Manager → /dashboard/manager
        ├── Employee → /dashboard/employee
        └── Candidate → /candidate-portal
```

### 5.2 Forgot Password Flow

```
User clicks "Forgot password" on login screen
  │
  ├── Enters registered email
  │
  ├── System always returns success (never reveals if email exists)
  │
  ├── If email exists → generate reset token (expires in 1 hour)
  │     └── Send email with reset link: /reset-password?token=<token>
  │
  └── User clicks link
        ├── Token valid → password reset form with strength indicator
        │     └── On submit → password updated, token invalidated, redirect to login
        └── Token invalid or expired → error, prompt to request again
```

### 5.3 Recruitment to Onboarding Flow

```
HR adds candidate to interview list
  │
  └── Assigns position, date, notes
        │
        └── After interview, HR marks status
              ├── Rejected → rejection email sent automatically
              └── Selected → selection email sent with portal login credentials
                    │
                    └── Candidate logs in to Candidate Portal
                          │
                          └── Completes 6-step onboarding wizard
                                ├── Step 1: Personal details
                                ├── Step 2: Address (current + permanent)
                                ├── Step 3: Education history
                                ├── Step 4: Document uploads (ID, certificates)
                                ├── Step 5: Bank account details
                                └── Step 6: Review and submit
                                      │
                                      └── HR receives notification
                                            │
                                            ├── HR reviews submitted details
                                            │
                                            ├── Rejects → candidate notified
                                            │
                                            └── Approves → candidate account becomes Employee
                                                  │
                                                  └── Candidate sees "Approved" screen
                                                        └── "Proceed to Dashboard" button
                                                              │
                                                              └── Employee dashboard loads
                                                                    └── Face enrollment banner shown (first priority)
```

### 5.4 Face Enrollment Flow

```
New employee logs into dashboard
  │
  └── Banner: "Complete your face enrollment — one-time setup"
        │
        └── Employee clicks "Enroll Face"
              │
              ├── Camera permission requested
              │     ├── Granted → live camera preview in circular frame
              │     └── Denied → placeholder with initials, note about camera
              │
              └── Employee clicks "Capture"
                    │
                    └── Preview shown → Employee reviews
                          ├── Retake → go back to camera
                          └── Submit
                                │
                                └── Face enrollment request sent to Manager's approval queue
                                      │
                                      ├── Employee sees "Pending verification" status on dashboard
                                      │
                                      └── Manager receives notification
                                            │
                                            ├── Manager reviews photo + employee details
                                            │
                                            ├── Rejects → employee notified, can re-enroll
                                            └── Approves → employee's face status = verified
                                                  └── Enrollment banner disappears from dashboard
```

### 5.5 Leave Application Flow

```
Employee opens Leave Management
  │
  └── Clicks "Apply Leave"
        │
        └── Selects leave type, from date, to date, reason
              │
              ├── System validates: sufficient balance, no overlapping requests
              │
              └── Submits
                    │
                    └── Manager receives notification + approval queue item
                          │
                          ├── Approves
                          │     ├── Employee notified
                          │     ├── Leave balance deducted
                          │     └── Attendance marked as "on leave" for those dates
                          │
                          └── Rejects (with reason)
                                ├── Employee notified
                                └── Balance unchanged
```

### 5.6 Payroll Flow

```
HR opens Employee profile → Salary tab
  │
  └── Configures salary structure
        ├── Sets gross monthly amount
        ├── Toggles earnings components on/off (Basic, HRA, Conveyance, LTA, Special Allowance)
        ├── Toggles deduction components on/off (PF, ESI, PT, TDS)
        ├── Changes component type (% of Gross / % of Basic / Fixed / Balance)
        └── Saves → all amounts recalculated live
              │
              └── HR runs payroll for a month
                    │
                    ├── System generates payslip per employee
                    │     ├── Applies salary structure
                    │     ├── Deducts LOP days if any
                    │     ├── Calculates gross, deductions, net pay
                    │     └── Generates payslip PDF with company header, employee details, amounts
                    │
                    └── Marks as Paid
                          ├── Employee receives notification
                          └── Employee can view/download payslip from My Payslips
```

### 5.7 Attendance — Clock In / Clock Out Flow

```
Employee / Manager logs in
  │
  └── Dashboard shows Clock In card
        │
        ├── Not clocked in → "Clock In" button
        │     └── Clicks Clock In
        │           ├── Records timestamp
        │           ├── Records IP address and location
        │           ├── Punch added to Today's Punches list
        │           └── Header chip shows live timer (counting up)
        │
        └── Clocked in → "Clock Out" button
              └── Clicks Clock Out
                    ├── Calculates session duration
                    ├── Records punch
                    ├── Timer stops
                    └── Daily total updated
```

### 5.8 Referral Flow

```
Employee opens Refer & Earn
  │
  └── Clicks "Refer Someone"
        │
        └── Submits: candidate name, email, phone, position, relationship, recommendation note
              │
              └── HR receives the referral
                    │
                    ├── HR reviews and adds candidate to interview list (linked to referral)
                    │
                    └── Referral status updates automatically as candidate progresses
                          ├── Submitted → Interview → Selected → Onboarded
                          │
                          └── On Onboarded (after 3 months probation)
                                │
                                └── HR approves referral bonus
                                      ├── Bonus amount added to referrer's next payslip
                                      └── Referrer notified: "₹15,000 bonus approved"
```

### 5.9 Expense Claim Flow

```
Employee submits expense claim
  │
  └── Fills: title, category, amount, date, description, attaches receipt
        │
        └── Submitted → Manager's approval queue
              │
              ├── Manager approves
              │     ├── Status → Approved
              │     ├── Employee notified
              │     └── Amount queued for next payroll reimbursement
              │
              └── Manager rejects (with reason)
                    ├── Status → Rejected
                    └── Employee notified with reason
```

### 5.10 Separation Flow

```
Employee submits resignation
  │
  └── Fills: last working date, reason
        │
        └── HR receives notification
              │
              ├── HR accepts resignation
              │     ├── Notice period begins
              │     └── Employee status → Resigning
              │
              └── On last working date
                    │
                    └── HR initiates FnF settlement
                          ├── Salary due calculated
                          ├── Leave encashment calculated
                          ├── Bonus due checked
                          ├── Loan/advance deductions applied
                          ├── Final settlement amount shown
                          │
                          └── HR marks FnF as Paid
                                ├── Employee receives FnF statement
                                └── Employee account deactivated
```

---

## 6. Feature Requirements

### 6.1 Authentication

| # | Requirement |
|---|-------------|
| AUTH-01 | Users log in with email and password |
| AUTH-02 | JWT access tokens expire in 15 minutes |
| AUTH-03 | Refresh tokens expire in 7 days and rotate on use |
| AUTH-04 | Account locked for 15 minutes after 5 failed login attempts |
| AUTH-05 | First login forces password change before accessing any feature |
| AUTH-06 | Forgot password sends a reset link valid for 1 hour |
| AUTH-07 | Reset link is single-use — invalidated after first use |
| AUTH-08 | Password must be minimum 8 characters with at least one uppercase, one number, one special character |
| AUTH-09 | All auth actions are logged in the audit log |
| AUTH-10 | Logout blacklists the refresh token server-side |
| AUTH-11 | On login, user is redirected to their role-specific dashboard |

### 6.2 Dashboards

Each role has a unique dashboard. Dashboards are the first screen seen after login.

| # | Requirement |
|---|-------------|
| DASH-01 | HR dashboard shows: recruitment funnel, pending approvals queue, department headcount chart, hiring trend chart, birthdays, anniversaries, live activity feed |
| DASH-02 | System Admin dashboard shows: module health indicators, active sessions chart, storage usage, recent login activity, audit log summary, license usage |
| DASH-03 | Manager dashboard shows: team live attendance status, clock-in card, pending approvals (face enrollments + leave), team performance metrics, celebrations |
| DASH-04 | Employee dashboard shows: clock-in card, face enrollment banner (if not enrolled), leave balance, recent requests, upcoming holidays, announcements |
| DASH-05 | All dashboards include real Chart.js charts — not placeholders |
| DASH-06 | Dashboards update dynamically — navigating back refreshes data |

### 6.3 Recruitment

| # | Requirement |
|---|-------------|
| REC-01 | HR can add candidates with name, email, phone, position, interview date |
| REC-02 | Referred candidates are linked to the referring employee |
| REC-03 | Each candidate has a status: Pending → Interview Scheduled → Selected / Rejected |
| REC-04 | HR can mark a candidate as Selected or Rejected from the interview list |
| REC-05 | On marking Selected, a selection email is sent automatically using the configured template |
| REC-06 | On marking Rejected, a rejection email is sent automatically |
| REC-07 | HR can view all sent emails in the Email Logs screen |
| REC-08 | Selected candidates receive portal login credentials via email |

### 6.4 Candidate Portal & Onboarding Wizard

| # | Requirement |
|---|-------------|
| ONB-01 | Candidates access a separate portal at a dedicated URL |
| ONB-02 | The portal shows the candidate's application status and any referral context |
| ONB-03 | The onboarding wizard has 6 steps: Personal, Address, Education, Documents, Bank, Review |
| ONB-04 | Wizard saves progress per step — candidate can return and continue |
| ONB-05 | Candidate can edit any step before final submission |
| ONB-06 | On submission, HR receives a notification and the candidate sees "Awaiting HR review" |
| ONB-07 | HR can approve or reject the submission |
| ONB-08 | On HR approval, candidate sees a celebration screen with "Proceed to Your Dashboard" button |
| ONB-09 | The approval screen lists first-day tasks: face enrollment, clock in, profile review |
| ONB-10 | Clicking "Proceed" transitions the user from Candidate to Employee role seamlessly |

### 6.5 Employee Management

| # | Requirement |
|---|-------------|
| EMP-01 | HR can add, edit, and deactivate employees |
| EMP-02 | Employee profile has 7 tabs: Profile, Salary, Payroll, Leave, Attendance, Approval Matrix, Benefits |
| EMP-03 | Profile tab has sub-sections: Basic Info, Contact, Address, Education, Experience, Documents, Bank, Emergency Contact |
| EMP-04 | All sub-sections are independently editable |
| EMP-05 | PAN, Aadhaar, and bank account numbers are masked in the UI by default |
| EMP-06 | HR can view the full employee list with search, filter by branch and department |
| EMP-07 | Employee list is exportable to Excel / CSV |
| EMP-08 | Each employee has a generated employee code (e.g. RSS00004D) |

### 6.6 Attendance

| # | Requirement |
|---|-------------|
| ATT-01 | Employees and managers can clock in and clock out |
| ATT-02 | Each clock-in/out records the timestamp, IP address, and location |
| ATT-03 | The header shows a live clock-in chip (timer counting up while clocked in) |
| ATT-04 | The attendance page shows today's punches, a monthly summary, and history table |
| ATT-05 | HR and Admin have an import view for bulk attendance data |
| ATT-06 | HR can manage invalid punches and un-punches |
| ATT-07 | Manager's attendance page includes a team live status grid |
| ATT-08 | Face enrollment is a one-time setup on hire — not required per clock-in |

### 6.7 Face Enrollment

| # | Requirement |
|---|-------------|
| FACE-01 | Face enrollment is a one-time process triggered at the start of employment |
| FACE-02 | The employee's dashboard shows a prominent banner when face is not enrolled |
| FACE-03 | The enrollment flow uses the device camera via WebRTC (getUserMedia) |
| FACE-04 | A preview with a mirror effect is shown before capture |
| FACE-05 | Employee can retake before submitting |
| FACE-06 | Submitted enrollment goes to the manager's approval queue |
| FACE-07 | Manager sees the photo, employee details, designation, and join date in the approval card |
| FACE-08 | Manager can approve or reject |
| FACE-09 | On rejection, employee is notified and can re-enroll |
| FACE-10 | On approval, the enrollment banner disappears from the dashboard |
| FACE-11 | Face status values: not_enrolled / pending / approved / rejected |

### 6.8 Leave Management

| # | Requirement |
|---|-------------|
| LVE-01 | The system supports multiple leave types: CL, EL, SL, ML, PL, and Wellness Leave |
| LVE-02 | Each leave type has configurable days per year, carry-forward rules, and pay status |
| LVE-03 | Employees can view their leave balance per type |
| LVE-04 | Employees apply for leave by selecting type, dates, and a reason |
| LVE-05 | The system validates sufficient balance before allowing submission |
| LVE-06 | Leave requests go to the manager for approval |
| LVE-07 | Manager can approve or reject with a reason |
| LVE-08 | Approved leave is reflected in the employee's attendance history |
| LVE-09 | HR has a full leave management view with all employees' requests |
| LVE-10 | HR can configure leave types and policy in Settings |

### 6.9 Salary & Payroll

| # | Requirement |
|---|-------------|
| PAY-01 | HR can configure a salary structure per employee |
| PAY-02 | The structure defines a gross monthly amount |
| PAY-03 | Earnings components (Basic, HRA, Conveyance, Medical, LTA, Special Allowance) are individually togglable |
| PAY-04 | Deduction components (PF, ESI, PT, TDS, Loan, Other) are individually togglable |
| PAY-05 | Each component has a calculation type: % of Gross, % of Basic, Fixed Amount, or Balance (auto-fills remainder) |
| PAY-06 | All amounts recalculate live as gross or any component is changed |
| PAY-07 | HR can generate payslips for a selected pay period |
| PAY-08 | Payslip shows company header, employee identity, earnings table, deductions table, net pay, amount in words |
| PAY-09 | Payslips are printable and downloadable as PDF |
| PAY-10 | Employees can view their own payslip history |
| PAY-11 | PF is calculated at 12% of Basic by default |
| PAY-12 | ESI is calculated at 1.75% of Gross by default |
| PAY-13 | Professional Tax is a fixed amount per state rules |

### 6.10 Expense Claims

| # | Requirement |
|---|-------------|
| EXP-01 | Employees and managers can submit expense claims |
| EXP-02 | Each claim requires: title, category (Travel/Meals/Equipment/Other), amount, date |
| EXP-03 | A receipt can be uploaded (PDF, JPG, PNG up to 5MB) |
| EXP-04 | Claims go to the manager for approval |
| EXP-05 | Manager and HR can approve or reject |
| EXP-06 | Approved claims are reimbursed in the next payroll cycle |
| EXP-07 | HR sees all employee expense claims |
| EXP-08 | Employees see only their own claims |
| EXP-09 | Claims are filterable by category and status |

### 6.11 Referral Program

| # | Requirement |
|---|-------------|
| REF-01 | Any active employee can submit a referral |
| REF-02 | Referral form captures: candidate name, email, phone, position, relationship, and a recommendation note |
| REF-03 | Referred candidates are tagged in the recruitment pipeline |
| REF-04 | Referral status tracks automatically: Submitted → Interview → Selected → Onboarded |
| REF-05 | Default bonus is ₹15,000, paid after 3 months of the referred candidate's probation |
| REF-06 | HR can configure the bonus amount and payout period in Settings |
| REF-07 | HR approves the bonus payout, which is added to the referrer's payslip |
| REF-08 | Employees can track all their referrals and bonus status on the Refer & Earn page |
| REF-09 | Candidates referred by an employee see a "Referred by [Name]" banner in their portal |
| REF-10 | HR sees all referrals with filter by status and a bonus approvals card |

### 6.12 Announcements

| # | Requirement |
|---|-------------|
| ANN-01 | HR, Admin, and Managers can post announcements |
| ANN-02 | Each announcement has a title, body, and category: General / Policy / Event / Celebration |
| ANN-03 | Announcements can be pinned — pinned posts appear at the top |
| ANN-04 | Visibility can be scoped to: All Employees / Department / Branch |
| ANN-05 | Employees can react to announcements |
| ANN-06 | Views and reaction counts are displayed |
| ANN-07 | HR can optionally trigger an email notification on posting |
| ANN-08 | All roles can see announcements relevant to them |

### 6.13 Document Center

| # | Requirement |
|---|-------------|
| DOC-01 | HR and Admin can upload company documents |
| DOC-02 | Documents have categories: Policy / Form / Template |
| DOC-03 | Each document shows name, file type, size, uploaded by, and date |
| DOC-04 | Employees can view and download documents |
| DOC-05 | Access level is configurable per document: All / HR Only / Manager and above |
| DOC-06 | Employees see only documents they are permitted to access |
| DOC-07 | Documents are filterable by category |

### 6.14 Branch Management

| # | Requirement |
|---|-------------|
| BRN-01 | Admin and HR can view all branches |
| BRN-02 | Each branch has a code, name, city, state, address, manager, and employee count |
| BRN-03 | A branch switcher in the header lets HR and Admin filter data by branch |
| BRN-04 | The Branches page shows a card per branch with an employee distribution chart |
| BRN-05 | Admin can add and edit branches |
| BRN-06 | Selecting "All Branches" shows aggregated data |

### 6.15 Separation & FnF

| # | Requirement |
|---|-------------|
| SEP-01 | Employees can initiate a resignation from the Separation module |
| SEP-02 | HR can initiate terminations or process retirements |
| SEP-03 | Notice period is tracked from submission to last working date |
| SEP-04 | HR processes the Full and Final settlement after the last working date |
| SEP-05 | FnF calculation includes: salary due, leave encashment, bonus, gratuity (if eligible), notice pay recovery, deductions |
| SEP-06 | HR marks FnF as Paid with a settlement date |
| SEP-07 | On completion, the employee's account is deactivated |

### 6.16 Settings

| # | Requirement |
|---|-------------|
| SET-01 | Settings is a card-based UI — 11 sections accessible via category filter |
| SET-02 | Company Info: name, logo, GST, CIN, registered address |
| SET-03 | Departments & Roles: add/edit/deactivate departments and job roles |
| SET-04 | Users & Permissions: manage user accounts, assign roles, force password resets |
| SET-05 | Leave Policy: configure leave types, carry-forward rules, approval chains |
| SET-06 | Payroll Rules: configure salary components, statutory rules, pay cycle |
| SET-07 | Attendance Rules: shift times, late-mark threshold, OT rules |
| SET-08 | Recruitment Config: interview stages, evaluation criteria |
| SET-09 | Email Templates: WYSIWYG editor for all 8 transactional emails with variable insertion |
| SET-10 | SMTP Settings: configure outgoing email server with test send |
| SET-11 | Notifications: configure which events trigger in-app and email notifications |
| SET-12 | Audit Log: immutable log of all system actions with user, timestamp, IP, and action |

### 6.17 Global Features (Cross-cutting)

| # | Requirement |
|---|-------------|
| GLB-01 | Global search in the header returns live results across employees, candidates, leave requests, and pages |
| GLB-02 | Notification panel (bell icon) shows categorised, unread-first notifications with mark-as-read |
| GLB-03 | Dark mode toggle in the header persists the user's preference |
| GLB-04 | Quick Actions floating button (bottom-right) shows role-specific shortcuts from any page |
| GLB-05 | All navigation sidebar badges reflect live counts (pending approvals, pending referrals, etc.) |
| GLB-06 | Every destructive action requires a confirmation step |
| GLB-07 | Toast notifications confirm all user actions |
| GLB-08 | Every action performed in the system is written to the audit log |

---

## 7. Non-Functional Requirements

### Performance

- API responses at P95 must be under 500ms
- Frontend first contentful paint must be under 1.5 seconds
- Largest contentful paint must be under 2.5 seconds
- Core Web Vitals must be in the "Good" range

### Scalability

- The API must be stateless and horizontally scalable
- No in-memory sessions — all state lives in the database or JWT
- File uploads go directly to S3 via presigned URLs — API server does not handle file bytes

### Availability

- 99.5% uptime SLA
- Scheduled maintenance only on Sundays between 2 AM and 4 AM IST
- Automated daily backups with 30-day retention

### Browser & Device Support

- Chrome 100+, Firefox 100+, Safari 15+, Edge 100+
- iOS Safari 15+, Android Chrome (latest two versions)
- All features must work on screens as narrow as 360px

### Accessibility

- WCAG 2.1 Level AA
- All interactive elements keyboard navigable
- All images have alt text
- Colour contrast minimum 4.5:1 for normal text
- Minimum tap target size 44x44px on mobile

### Responsive Behaviour

| Breakpoint | Behaviour |
|-----------|-----------|
| < 480px | Single column, stat cards stack, tables scroll horizontally |
| 480–768px | 2-column stat grids, sidebar hidden behind hamburger |
| 768–900px | Sidebar still behind hamburger, content area full width |
| 900px+ | Sidebar permanently visible, multi-column layouts |

### Data & Compliance

- Currency in INR (Indian Rupee, ₹)
- Date format: DD/MM/YYYY throughout
- Timezone: Asia/Kolkata (IST, UTC+5:30) for all timestamps
- PF calculated at 12% of Basic — as per Indian Provident Fund Act
- ESI calculated at 1.75% of Gross — as per Indian ESIC Act
- Maternity leave at 26 weeks — as per Maternity Benefit Act
- PAN and Aadhaar masked in UI by default — only unmasked on explicit user action
- Employee records retained for 7 years post-separation
- Audit logs retained for 5 years

---

## 8. Security Requirements

### Authentication & Session

- Passwords hashed with bcrypt at cost factor 12 minimum
- Passwords never stored in plain text, never logged, never returned in any API response
- JWT access tokens expire in 15 minutes
- Refresh tokens expire in 7 days with rotation on every use
- Refresh tokens are stored in httpOnly cookies — inaccessible to JavaScript
- On logout, the refresh token is blacklisted server-side (Redis TTL)
- Brute-force protection: account locked for 15 minutes after 5 consecutive failed attempts
- Locked account message shows time remaining, not the reason

### Authorisation

- Every API endpoint enforces role-based access control at the middleware level
- Frontend visibility is cosmetic only — removing a UI element does not grant access
- Data scoping is server-side: managers receive only their direct reports' data, never others
- Admin-level actions (delete, run payroll, approve bonus) require the user to confirm their password

### Data Security

- All data in transit over HTTPS only. HTTP redirects to HTTPS
- HSTS headers with 1-year max-age in production
- Personally identifiable information (PAN, Aadhaar, bank account number) encrypted at rest using AES-256
- Secrets (DB password, email credentials, secret key) live only in environment variables — never in source code
- File uploads validated for: allowed types (PDF, JPG, PNG, DOCX), size limit (5MB), no executable content

### Input Validation

- All inputs validated server-side using a schema validation library (Zod or Joi)
- Parameterised queries only — string concatenation into SQL is forbidden
- HTML output escaped — dangerouslySetInnerHTML never used without sanitisation
- API rate limited: 100 requests/minute per IP for public endpoints, 1000 for authenticated

### Security Headers

All responses include:

- `Content-Security-Policy` — restricts script and style sources
- `X-Frame-Options: DENY` — prevents clickjacking
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `CORS` — whitelist only known frontend origins in production

### Audit & Monitoring

- Every action is written to the immutable audit log: who, what, when, from which IP
- Failed login attempts are logged
- Application errors are shipped to centralised logging
- Alerts fire for: error rate above 1%, P95 latency above 2s, disk above 80%

---

## 9. Integration Requirements

### Email

- All transactional emails sent via configured SMTP server
- 8 email types: selection, rejection, credentials, HR approval, welcome, payslip, leave approved, separation
- All templates configurable via Settings → Email Templates
- Email sending is asynchronous — queued in background, not blocking the request

### File Storage

- All uploaded files stored in cloud object storage (AWS S3 or compatible)
- Files referenced by URL in the database — never stored on the application server
- Presigned URLs used for uploads — files go directly from browser to storage

### Background Jobs

- Payroll processing, bulk email dispatch, and notification generation run as background jobs
- Jobs are queued — failures retry automatically with exponential backoff

---

## 10. Out of Scope — V1

The following are explicitly excluded from this release:

- Native iOS or Android applications — the responsive web is sufficient
- Performance management — OKRs, KPI tracking, 360-degree reviews
- Training and learning management — course catalogue, completion tracking
- Asset management — laptop, ID card, equipment tracking
- Hardware biometric integration — face enrollment uses the device camera only, not biometric hardware
- AI-powered features — chatbot, resume parsing, automated candidate screening
- Third-party HRMS integrations — no SAP, Workday, or Zoho People connectors
- Multi-currency or multi-language support
- Mobile push notifications — in-app and email only

---

## 11. Constraints & Assumptions

### Constraints

- The system must run on standard cloud infrastructure — no proprietary or on-premise-only dependencies
- The frontend must be a standard web application — no browser extensions required
- All third-party libraries must have active maintenance and permissive licensing (MIT / Apache 2.0)

### Assumptions

- All employees have a unique work email address — this is the login identifier
- Branch managers are themselves employees in the system
- The client will confirm field-level specifications during sprint planning — this PRD intentionally omits individual form field names and validation rules
- The referral bonus amount (₹15,000) and payout period (3 months) are configurable by HR — the defaults are as specified but the client may change them
- The statutory deduction rates (PF 12%, ESI 1.75%) are correct as of the time of writing — if rates change, they must be updated in Settings
- Email delivery will be set up by the client — SMTP credentials will be provided before email features go live

---

## 12. Glossary

| Term | Definition |
|------|-----------|
| CL | Casual Leave — general-purpose short leave |
| CTC | Cost to Company — total annual compensation |
| EL | Earned Leave — accrued monthly, encashable on separation |
| ESI | Employee State Insurance — statutory deduction at 1.75% of gross |
| FnF | Full and Final settlement — all financial dues cleared on separation |
| HRMS | Human Resource Management System |
| HSTS | HTTP Strict Transport Security — forces HTTPS on all connections |
| IST | Indian Standard Time (UTC+5:30) |
| JWT | JSON Web Token — stateless authentication mechanism |
| LOP | Loss of Pay — unpaid days deducted from monthly salary |
| LTA | Leave Travel Allowance — salary component for travel |
| ML | Maternity Leave — 26 weeks as per Maternity Benefit Act |
| OT | Overtime — hours worked beyond standard shift |
| P95 | 95th percentile response time — 95% of requests complete within this time |
| PAN | Permanent Account Number — Indian tax identification |
| PF | Provident Fund — statutory deduction at 12% of basic salary |
| PL | Paternity Leave — 5 days for new fathers |
| PRD | Product Requirements Document — this document |
| PT | Professional Tax — state-level fixed deduction |
| RBAC | Role-Based Access Control — server-side permission enforcement |
| SL | Sick Leave — medical leave |
| SMTP | Simple Mail Transfer Protocol — outgoing email server |
| TDS | Tax Deducted at Source — income tax withheld from salary |
| UAT | User Acceptance Testing — client validates before go-live |
| V1 | Version 1 — this release |
| WCAG | Web Content Accessibility Guidelines |
| WL | Wellness Leave — mental health and personal wellness leave |

---

*Royal Staffing Services LLP — Royal HRMS PRD v1.0 — Confidential*
