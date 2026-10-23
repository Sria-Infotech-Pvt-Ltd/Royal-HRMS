# Employee onboarding UAT report

**Run date:** 23 October 2026
**Environment:** configured Neon test database (`neondb`)
**Overall result:** **PASS WITH SCOPE LIMITATIONS**

## Scope and data

Created and exercised 100 deterministic synthetic employees on the reserved `example.com` domain. The 100 records are split across four offices (25 each) and three employment types (70 permanent, 20 contract, 10 intern). All 100 now have completed onboarding and assessment status.

The data set contains no real employee identity or banking details. The UAT does not initiate bank transfers. Payroll cycles were marked paid in the application for workflow validation; this is not evidence of a real funds settlement.

## Results

| Area | Result |
|---|---:|
| Employees / unique employee IDs | 100 / 100 |
| Employee and profile fields inspected | 44 + 80 per employee; 12,400 field checks total |
| Required fields missing / field validation failures | 0 / 0 |
| Optional blank field occurrences | 3,153 (optional fields are allowed to remain blank) |
| Branch assignment and active placement | 100 / 100 |
| Active salary configurations with positive annual CTC | 100 / 100 |
| Attendance records / punches / corrections | 11,400 / 14,375 / 199 |
| Attendance statuses | 6,459 present; 3,200 weekly off; 479 late; 463 on leave; 300 holiday; 200 half day; 200 absent; 99 incomplete |
| Leave balances / requests | 800 balances / 288 requests; no negative total balances |
| Leave request statuses | 288 approved |
| Leave types | 100 casual; 91 earned; 97 sick requests |
| Required employee documents | 700 uploaded; all 700 verified and have a file and positive file size (7 types × 100 employees) |
| Payroll | 8 tagged cycles paid; 200 UAT payslips paid; all 200 have positive net pay |
| Payslip PDF renderer | 200 / 200 rendered; all outputs had a valid `%PDF-` header and were non-empty |

The app renders payslip PDFs on demand, so the payslip rows' `payslip_pdf` storage fields remain empty by design. The report validates the renderer output instead of treating an unpersisted PDF as a failed payroll calculation.

## Field audit

Every concrete field on `User` and `EmployeeProfile` was checked for presence or an allowed optional blank, model choices, maximum string length, email validity, and the configured PAN, Aadhaar, and IFSC formats. No decrypted values are included in the audit file. All 100 rows passed the required-field and validation checks.

The report keeps employee references as `UAT-001` through `UAT-100`; the accompanying lifecycle CSV maps each reference to per-employee setup and transaction counts. The field CSV has one row per employee per concrete field, for 12,400 rows total.

## Workflow and test coverage

- A 100-person rehearsal completed and rolled back before data was persisted.
- The persistent seed was run idempotently in Neon. The final rerun created no duplicate employees, attendance, leave requests, or payroll cycles; it corrected missing work location/work mode and completed status on the synthetic records.
- Documents were submitted through the employee profile document endpoint and verified through the onboarding document review endpoint.
- Attendance, leave, and payroll calculations ran through the configured application seed workflows. All eight test cycles completed in paid state.
- Focused roster/profile automated checks: **15 passed**.
- Hire Wizard regression suite: **44 passed** against its existing isolated retained test database. The test process disabled HTTPS redirection only for the local HTTP test client; application production security settings were not changed. The unadjusted invocation returned redirects because Django's test runner forces `DEBUG=False` and activates the production HTTPS middleware.

## Scope limitations

The 100 employees were created through the idempotent synthetic workforce seed workflow rather than each being hired through a separate HireAction Wizard session. The Hire Wizard path was covered by its 44-test regression suite, but was not used to create the 100 persistent UAT employees. The test database has no active SMTP configuration, so welcome credential email delivery was not verified; email failures were logged during successful hire completion tests. Payroll was validated through payslip calculation, paid state, and PDF rendering. No external payment settlement, live employee notification, or production employee data was involved.

## Artifacts

- [Employee-by-field audit CSV](UAT_EMPLOYEE_FIELD_AUDIT_2026-10-23.csv)
- [Per-employee lifecycle audit CSV](UAT_EMPLOYEE_LIFECYCLE_AUDIT_2026-10-23.csv)
- [Read-only audit generator](../backend/scripts/uat_employee_audit.py)
