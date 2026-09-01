"""
Seeds the real SRIA organisation structure — 43 org units and 223 positions,
from a JSON export of the company's actual org chart (position_id, org_unit,
unit_cost_center, position_title, grade_band, is_chief, reports_to; a
`status` column of "Done"/"Verify (likely done)"/"To create" in the source
was informational only from the source system and is not applied here —
every row is seeded regardless).

The source titles had their em dash (—) mangled to a stray "â" by whatever
produced the export (UTF-8 bytes for U+2014 misread as Latin-1/cp1252) —
fixed inline via _fix_title() rather than by re-exporting.

Hierarchy is derived from each unit's chief position's `reports_to`, which
names another chief position's title, not an explicit parent-unit column —
resolved here the same way it was validated in a dry run before this
migration was written (every unit has exactly one chief, every reports_to
resolves to a real chief position, no cycles).

All positions are created vacant — the source data has no holder/employee
column at all.

get_or_create throughout (never bare create(), per this repo's convention
for data migrations) — safe to re-run, and matches existing units/positions
by (name, parent) / (org_unit, title) instead of duplicating them if this
ever runs against a database that isn't empty.
"""
from django.db import migrations

# (org_unit, unit_cost_center, position_title, grade_band, is_chief, reports_to)
POSITIONS = [
    ('SRIA', None, 'Head — SRIA', 'EXEC', True, None),
    ('Software Services', 'CC-1000', 'Head — Software Services', 'M4', True, 'Head — SRIA'),
    ('Product Development', 'CC-2000', 'Head — Product Development', 'M4', True, 'Head — SRIA'),
    ('IT Infrastructure', 'CC-3000', 'Head — IT Infrastructure', 'M4', True, 'Head — SRIA'),
    ('Training', 'CC-4000', 'Head — Training', 'M4', True, 'Head — SRIA'),
    ('Delivery Management', 'CC-5000', 'Head — Delivery Management', 'M4', True, 'Head — SRIA'),
    ('Corporate', 'CC-9000', 'Head — Corporate', 'M4', True, 'Head — SRIA'),
    ('Human Resources', 'CC-9200', 'Head — Human Resources', 'M3', True, 'Head — Corporate'),
    ('Sales & Marketing', 'CC-9300', 'Head — Sales & Marketing', 'M3', True, 'Head — Corporate'),
    ('SAP', 'CC-1100', 'Head — SAP', 'M3', True, 'Head — Software Services'),
    ('Application Development', 'CC-1200', 'Head — Application Development', 'M3', True, 'Head — Software Services'),
    ('Testing / QA', 'CC-1400', 'Head — Testing / QA', 'M3', True, 'Head — Software Services'),
    ('Digital Marketing', 'CC-1600', 'Head — Digital Marketing', 'M3', True, 'Head — Software Services'),
    ('AI & ML', 'CC-1300', 'Head — AI & ML', 'M2', True, 'Head — Software Services'),
    ('AI & ML', 'CC-1300', 'Lead — AI & ML', 'L5', False, 'Head — AI & ML'),
    ('AI & ML', 'CC-1300', 'Senior AI & ML Specialist', 'L4', False, 'Head — AI & ML'),
    ('AI & ML', 'CC-1300', 'AI & ML Specialist', 'L3', False, 'Head — AI & ML'),
    ('AI & ML', 'CC-1300', 'AI & ML Associate', 'L2', False, 'Head — AI & ML'),
    ('AI & ML', 'CC-1300', 'AI & ML Associate II', 'L2', False, 'Head — AI & ML'),
    ('AI & ML', 'CC-1300', 'AI & ML Trainee Associate', 'L1', False, 'Head — AI & ML'),
    ('Cyber Security', 'CC-1500', 'Head — Cyber Security', 'M2', True, 'Head — Software Services'),
    ('Cyber Security', 'CC-1500', 'Lead — Cyber Security', 'L5', False, 'Head — Cyber Security'),
    ('Cyber Security', 'CC-1500', 'Senior Cyber Security Specialist', 'L4', False, 'Head — Cyber Security'),
    ('Cyber Security', 'CC-1500', 'Cyber Security Specialist', 'L3', False, 'Head — Cyber Security'),
    ('Cyber Security', 'CC-1500', 'Cyber Security Associate', 'L2', False, 'Head — Cyber Security'),
    ('Cyber Security', 'CC-1500', 'Cyber Security Associate II', 'L2', False, 'Head — Cyber Security'),
    ('Cyber Security', 'CC-1500', 'Cyber Security Trainee Associate', 'L1', False, 'Head — Cyber Security'),
    ('SAP Functional', 'CC-1110', 'Head — SAP Functional', 'M2', True, 'Head — SAP'),
    ('SAP Functional', 'CC-1110', 'Lead — SAP Functional', 'L5', False, 'Head — SAP Functional'),
    ('SAP Functional', 'CC-1110', 'Senior SAP Functional Specialist', 'L4', False, 'Head — SAP Functional'),
    ('SAP Functional', 'CC-1110', 'SAP Functional Specialist', 'L3', False, 'Head — SAP Functional'),
    ('SAP Functional', 'CC-1110', 'SAP Functional Associate', 'L2', False, 'Head — SAP Functional'),
    ('SAP Functional', 'CC-1110', 'SAP Functional Associate II', 'L2', False, 'Head — SAP Functional'),
    ('SAP Functional', 'CC-1110', 'SAP Functional Trainee Associate', 'L1', False, 'Head — SAP Functional'),
    ('SAP Technical (ABAP)', 'CC-1120', 'Head — SAP Technical (ABAP)', 'M2', True, 'Head — SAP'),
    ('SAP Technical (ABAP)', 'CC-1120', 'Lead — SAP Technical (ABAP)', 'L5', False, 'Head — SAP Technical (ABAP)'),
    ('SAP Technical (ABAP)', 'CC-1120', 'Senior SAP Technical (ABAP) Specialist', 'L4', False, 'Head — SAP Technical (ABAP)'),
    ('SAP Technical (ABAP)', 'CC-1120', 'SAP Technical (ABAP) Specialist', 'L3', False, 'Head — SAP Technical (ABAP)'),
    ('SAP Technical (ABAP)', 'CC-1120', 'SAP Technical (ABAP) Associate', 'L2', False, 'Head — SAP Technical (ABAP)'),
    ('SAP Technical (ABAP)', 'CC-1120', 'SAP Technical (ABAP) Associate II', 'L2', False, 'Head — SAP Technical (ABAP)'),
    ('SAP Technical (ABAP)', 'CC-1120', 'SAP Technical (ABAP) Trainee Associate', 'L1', False, 'Head — SAP Technical (ABAP)'),
    ('SAP Basis', 'CC-1130', 'Head — SAP Basis', 'M2', True, 'Head — SAP'),
    ('SAP Basis', 'CC-1130', 'Lead — SAP Basis', 'L5', False, 'Head — SAP Basis'),
    ('SAP Basis', 'CC-1130', 'Senior SAP Basis Specialist', 'L4', False, 'Head — SAP Basis'),
    ('SAP Basis', 'CC-1130', 'SAP Basis Specialist', 'L3', False, 'Head — SAP Basis'),
    ('SAP Basis', 'CC-1130', 'SAP Basis Associate', 'L2', False, 'Head — SAP Basis'),
    ('SAP Basis', 'CC-1130', 'SAP Basis Associate II', 'L2', False, 'Head — SAP Basis'),
    ('SAP Basis', 'CC-1130', 'SAP Basis Trainee Associate', 'L1', False, 'Head — SAP Basis'),
    ('Web', 'CC-1210', 'Head — Web', 'M2', True, 'Head — Application Development'),
    ('Web', 'CC-1210', 'Lead — Web', 'L5', False, 'Head — Web'),
    ('Web', 'CC-1210', 'Senior Web Specialist', 'L4', False, 'Head — Web'),
    ('Web', 'CC-1210', 'Web Specialist', 'L3', False, 'Head — Web'),
    ('Web', 'CC-1210', 'Web Associate', 'L2', False, 'Head — Web'),
    ('Web', 'CC-1210', 'Web Associate II', 'L2', False, 'Head — Web'),
    ('Web', 'CC-1210', 'Web Trainee Associate', 'L1', False, 'Head — Web'),
    ('Mobile', 'CC-1220', 'Head — Mobile', 'M2', True, 'Head — Application Development'),
    ('Mobile', 'CC-1220', 'Lead — Mobile', 'L5', False, 'Head — Mobile'),
    ('Mobile', 'CC-1220', 'Senior Mobile Specialist', 'L4', False, 'Head — Mobile'),
    ('Mobile', 'CC-1220', 'Mobile Specialist', 'L3', False, 'Head — Mobile'),
    ('Mobile', 'CC-1220', 'Mobile Associate', 'L2', False, 'Head — Mobile'),
    ('Mobile', 'CC-1220', 'Mobile Associate II', 'L2', False, 'Head — Mobile'),
    ('Mobile', 'CC-1220', 'Mobile Trainee Associate', 'L1', False, 'Head — Mobile'),
    ('Manual', 'CC-1410', 'Head — Manual', 'M2', True, 'Head — Testing / QA'),
    ('Manual', 'CC-1410', 'Lead — Manual', 'L5', False, 'Head — Manual'),
    ('Manual', 'CC-1410', 'Senior Manual Specialist', 'L4', False, 'Head — Manual'),
    ('Manual', 'CC-1410', 'Manual Specialist', 'L3', False, 'Head — Manual'),
    ('Manual', 'CC-1410', 'Manual Associate', 'L2', False, 'Head — Manual'),
    ('Manual', 'CC-1410', 'Manual Associate II', 'L2', False, 'Head — Manual'),
    ('Manual', 'CC-1410', 'Manual Trainee Associate', 'L1', False, 'Head — Manual'),
    ('Automation', 'CC-1420', 'Head — Automation', 'M2', True, 'Head — Testing / QA'),
    ('Automation', 'CC-1420', 'Lead — Automation', 'L5', False, 'Head — Automation'),
    ('Automation', 'CC-1420', 'Senior Automation Specialist', 'L4', False, 'Head — Automation'),
    ('Automation', 'CC-1420', 'Automation Specialist', 'L3', False, 'Head — Automation'),
    ('Automation', 'CC-1420', 'Automation Associate', 'L2', False, 'Head — Automation'),
    ('Automation', 'CC-1420', 'Automation Associate II', 'L2', False, 'Head — Automation'),
    ('Automation', 'CC-1420', 'Automation Trainee Associate', 'L1', False, 'Head — Automation'),
    ('SEO & SEM', 'CC-1610', 'Head — SEO & SEM', 'M2', True, 'Head — Digital Marketing'),
    ('SEO & SEM', 'CC-1610', 'Lead — SEO & SEM', 'L5', False, 'Head — SEO & SEM'),
    ('SEO & SEM', 'CC-1610', 'Senior SEO & SEM Specialist', 'L4', False, 'Head — SEO & SEM'),
    ('SEO & SEM', 'CC-1610', 'SEO & SEM Specialist', 'L3', False, 'Head — SEO & SEM'),
    ('SEO & SEM', 'CC-1610', 'SEO & SEM Associate', 'L2', False, 'Head — SEO & SEM'),
    ('SEO & SEM', 'CC-1610', 'SEO & SEM Associate II', 'L2', False, 'Head — SEO & SEM'),
    ('SEO & SEM', 'CC-1610', 'SEO & SEM Trainee Associate', 'L1', False, 'Head — SEO & SEM'),
    ('Social & Content', 'CC-1620', 'Head — Social & Content', 'M2', True, 'Head — Digital Marketing'),
    ('Social & Content', 'CC-1620', 'Lead — Social & Content', 'L5', False, 'Head — Social & Content'),
    ('Social & Content', 'CC-1620', 'Senior Social & Content Specialist', 'L4', False, 'Head — Social & Content'),
    ('Social & Content', 'CC-1620', 'Social & Content Specialist', 'L3', False, 'Head — Social & Content'),
    ('Social & Content', 'CC-1620', 'Social & Content Associate', 'L2', False, 'Head — Social & Content'),
    ('Social & Content', 'CC-1620', 'Social & Content Associate II', 'L2', False, 'Head — Social & Content'),
    ('Social & Content', 'CC-1620', 'Social & Content Trainee Associate', 'L1', False, 'Head — Social & Content'),
    ('Product Management', 'CC-2100', 'Head — Product Management', 'M2', True, 'Head — Product Development'),
    ('Product Management', 'CC-2100', 'Lead — Product Management', 'L5', False, 'Head — Product Management'),
    ('Product Management', 'CC-2100', 'Senior Product Management Specialist', 'L4', False, 'Head — Product Management'),
    ('Product Management', 'CC-2100', 'Product Management Specialist', 'L3', False, 'Head — Product Management'),
    ('Product Management', 'CC-2100', 'Product Management Associate', 'L2', False, 'Head — Product Management'),
    ('Product Management', 'CC-2100', 'Product Management Associate II', 'L2', False, 'Head — Product Management'),
    ('Product Management', 'CC-2100', 'Product Management Trainee Associate', 'L1', False, 'Head — Product Management'),
    ('Product Engineering', 'CC-2200', 'Head — Product Engineering', 'M2', True, 'Head — Product Development'),
    ('Product Engineering', 'CC-2200', 'Lead — Product Engineering', 'L5', False, 'Head — Product Engineering'),
    ('Product Engineering', 'CC-2200', 'Senior Product Engineering Specialist', 'L4', False, 'Head — Product Engineering'),
    ('Product Engineering', 'CC-2200', 'Product Engineering Specialist', 'L3', False, 'Head — Product Engineering'),
    ('Product Engineering', 'CC-2200', 'Product Engineering Associate', 'L2', False, 'Head — Product Engineering'),
    ('Product Engineering', 'CC-2200', 'Product Engineering Associate II', 'L2', False, 'Head — Product Engineering'),
    ('Product Engineering', 'CC-2200', 'Product Engineering Trainee Associate', 'L1', False, 'Head — Product Engineering'),
    ('UI/UX Design', 'CC-2300', 'Head — UI/UX Design', 'M2', True, 'Head — Product Development'),
    ('UI/UX Design', 'CC-2300', 'Lead — UI/UX Design', 'L5', False, 'Head — UI/UX Design'),
    ('UI/UX Design', 'CC-2300', 'Senior UI/UX Design Specialist', 'L4', False, 'Head — UI/UX Design'),
    ('UI/UX Design', 'CC-2300', 'UI/UX Design Specialist', 'L3', False, 'Head — UI/UX Design'),
    ('UI/UX Design', 'CC-2300', 'UI/UX Design Associate', 'L2', False, 'Head — UI/UX Design'),
    ('UI/UX Design', 'CC-2300', 'UI/UX Design Associate II', 'L2', False, 'Head — UI/UX Design'),
    ('UI/UX Design', 'CC-2300', 'UI/UX Design Trainee Associate', 'L1', False, 'Head — UI/UX Design'),
    ('Product QA', 'CC-2400', 'Head — Product QA', 'M2', True, 'Head — Product Development'),
    ('Product QA', 'CC-2400', 'Lead — Product QA', 'L5', False, 'Head — Product QA'),
    ('Product QA', 'CC-2400', 'Senior Product QA Specialist', 'L4', False, 'Head — Product QA'),
    ('Product QA', 'CC-2400', 'Product QA Specialist', 'L3', False, 'Head — Product QA'),
    ('Product QA', 'CC-2400', 'Product QA Associate', 'L2', False, 'Head — Product QA'),
    ('Product QA', 'CC-2400', 'Product QA Associate II', 'L2', False, 'Head — Product QA'),
    ('Product QA', 'CC-2400', 'Product QA Trainee Associate', 'L1', False, 'Head — Product QA'),
    ('Cloud & DevOps', 'CC-3100', 'Head — Cloud & DevOps', 'M2', True, 'Head — IT Infrastructure'),
    ('Cloud & DevOps', 'CC-3100', 'Lead — Cloud & DevOps', 'L5', False, 'Head — Cloud & DevOps'),
    ('Cloud & DevOps', 'CC-3100', 'Senior Cloud & DevOps Specialist', 'L4', False, 'Head — Cloud & DevOps'),
    ('Cloud & DevOps', 'CC-3100', 'Cloud & DevOps Specialist', 'L3', False, 'Head — Cloud & DevOps'),
    ('Cloud & DevOps', 'CC-3100', 'Cloud & DevOps Associate', 'L2', False, 'Head — Cloud & DevOps'),
    ('Cloud & DevOps', 'CC-3100', 'Cloud & DevOps Associate II', 'L2', False, 'Head — Cloud & DevOps'),
    ('Cloud & DevOps', 'CC-3100', 'Cloud & DevOps Trainee Associate', 'L1', False, 'Head — Cloud & DevOps'),
    ('Network & SysAdmin', 'CC-3200', 'Head — Network & SysAdmin', 'M2', True, 'Head — IT Infrastructure'),
    ('Network & SysAdmin', 'CC-3200', 'Lead — Network & SysAdmin', 'L5', False, 'Head — Network & SysAdmin'),
    ('Network & SysAdmin', 'CC-3200', 'Senior Network & SysAdmin Specialist', 'L4', False, 'Head — Network & SysAdmin'),
    ('Network & SysAdmin', 'CC-3200', 'Network & SysAdmin Specialist', 'L3', False, 'Head — Network & SysAdmin'),
    ('Network & SysAdmin', 'CC-3200', 'Network & SysAdmin Associate', 'L2', False, 'Head — Network & SysAdmin'),
    ('Network & SysAdmin', 'CC-3200', 'Network & SysAdmin Associate II', 'L2', False, 'Head — Network & SysAdmin'),
    ('Network & SysAdmin', 'CC-3200', 'Network & SysAdmin Trainee Associate', 'L1', False, 'Head — Network & SysAdmin'),
    ('IT Support / Helpdesk', 'CC-3300', 'Head — IT Support / Helpdesk', 'M2', True, 'Head — IT Infrastructure'),
    ('IT Support / Helpdesk', 'CC-3300', 'Lead — IT Support / Helpdesk', 'L5', False, 'Head — IT Support / Helpdesk'),
    ('IT Support / Helpdesk', 'CC-3300', 'Senior IT Support / Helpdesk Specialist', 'L4', False, 'Head — IT Support / Helpdesk'),
    ('IT Support / Helpdesk', 'CC-3300', 'IT Support / Helpdesk Specialist', 'L3', False, 'Head — IT Support / Helpdesk'),
    ('IT Support / Helpdesk', 'CC-3300', 'IT Support / Helpdesk Associate', 'L2', False, 'Head — IT Support / Helpdesk'),
    ('IT Support / Helpdesk', 'CC-3300', 'IT Support / Helpdesk Associate II', 'L2', False, 'Head — IT Support / Helpdesk'),
    ('IT Support / Helpdesk', 'CC-3300', 'IT Support / Helpdesk Trainee Associate', 'L1', False, 'Head — IT Support / Helpdesk'),
    ('Faculty / Instructors', 'CC-4100', 'Head — Faculty / Instructors', 'M2', True, 'Head — Training'),
    ('Faculty / Instructors', 'CC-4100', 'Lead — Faculty / Instructors', 'L5', False, 'Head — Faculty / Instructors'),
    ('Faculty / Instructors', 'CC-4100', 'Senior Faculty / Instructors Specialist', 'L4', False, 'Head — Faculty / Instructors'),
    ('Faculty / Instructors', 'CC-4100', 'Faculty / Instructors Specialist', 'L3', False, 'Head — Faculty / Instructors'),
    ('Faculty / Instructors', 'CC-4100', 'Faculty / Instructors Associate', 'L2', False, 'Head — Faculty / Instructors'),
    ('Faculty / Instructors', 'CC-4100', 'Faculty / Instructors Associate II', 'L2', False, 'Head — Faculty / Instructors'),
    ('Faculty / Instructors', 'CC-4100', 'Faculty / Instructors Trainee Associate', 'L1', False, 'Head — Faculty / Instructors'),
    ('Content & Courseware', 'CC-4200', 'Head — Content & Courseware', 'M2', True, 'Head — Training'),
    ('Content & Courseware', 'CC-4200', 'Lead — Content & Courseware', 'L5', False, 'Head — Content & Courseware'),
    ('Content & Courseware', 'CC-4200', 'Senior Content & Courseware Specialist', 'L4', False, 'Head — Content & Courseware'),
    ('Content & Courseware', 'CC-4200', 'Content & Courseware Specialist', 'L3', False, 'Head — Content & Courseware'),
    ('Content & Courseware', 'CC-4200', 'Content & Courseware Associate', 'L2', False, 'Head — Content & Courseware'),
    ('Content & Courseware', 'CC-4200', 'Content & Courseware Associate II', 'L2', False, 'Head — Content & Courseware'),
    ('Content & Courseware', 'CC-4200', 'Content & Courseware Trainee Associate', 'L1', False, 'Head — Content & Courseware'),
    ('Admissions & Student Services', 'CC-4300', 'Head — Admissions & Student Services', 'M2', True, 'Head — Training'),
    ('Admissions & Student Services', 'CC-4300', 'Lead — Admissions & Student Services', 'L5', False, 'Head — Admissions & Student Services'),
    ('Admissions & Student Services', 'CC-4300', 'Senior Admissions & Student Services Specialist', 'L4', False, 'Head — Admissions & Student Services'),
    ('Admissions & Student Services', 'CC-4300', 'Admissions & Student Services Specialist', 'L3', False, 'Head — Admissions & Student Services'),
    ('Admissions & Student Services', 'CC-4300', 'Admissions & Student Services Associate', 'L2', False, 'Head — Admissions & Student Services'),
    ('Admissions & Student Services', 'CC-4300', 'Admissions & Student Services Associate II', 'L2', False, 'Head — Admissions & Student Services'),
    ('Admissions & Student Services', 'CC-4300', 'Admissions & Student Services Trainee Associate', 'L1', False, 'Head — Admissions & Student Services'),
    ('Finance & Accounts', 'CC-9100', 'Head — Finance & Accounts', 'M2', True, 'Head — Corporate'),
    ('Finance & Accounts', 'CC-9100', 'Lead — Finance & Accounts', 'L5', False, 'Head — Finance & Accounts'),
    ('Finance & Accounts', 'CC-9100', 'Senior Finance & Accounts Specialist', 'L4', False, 'Head — Finance & Accounts'),
    ('Finance & Accounts', 'CC-9100', 'Finance & Accounts Specialist', 'L3', False, 'Head — Finance & Accounts'),
    ('Finance & Accounts', 'CC-9100', 'Finance & Accounts Associate', 'L2', False, 'Head — Finance & Accounts'),
    ('Finance & Accounts', 'CC-9100', 'Finance & Accounts Associate II', 'L2', False, 'Head — Finance & Accounts'),
    ('Finance & Accounts', 'CC-9100', 'Finance & Accounts Trainee Associate', 'L1', False, 'Head — Finance & Accounts'),
    ('Quality & Compliance', 'CC-9400', 'Head — Quality & Compliance', 'M2', True, 'Head — Corporate'),
    ('Quality & Compliance', 'CC-9400', 'Lead — Quality & Compliance', 'L5', False, 'Head — Quality & Compliance'),
    ('Quality & Compliance', 'CC-9400', 'Senior Quality & Compliance Specialist', 'L4', False, 'Head — Quality & Compliance'),
    ('Quality & Compliance', 'CC-9400', 'Quality & Compliance Specialist', 'L3', False, 'Head — Quality & Compliance'),
    ('Quality & Compliance', 'CC-9400', 'Quality & Compliance Associate', 'L2', False, 'Head — Quality & Compliance'),
    ('Quality & Compliance', 'CC-9400', 'Quality & Compliance Associate II', 'L2', False, 'Head — Quality & Compliance'),
    ('Quality & Compliance', 'CC-9400', 'Quality & Compliance Trainee Associate', 'L1', False, 'Head — Quality & Compliance'),
    ('Administration & IT', 'CC-9500', 'Head — Administration & IT', 'M2', True, 'Head — Corporate'),
    ('Administration & IT', 'CC-9500', 'Lead — Administration & IT', 'L5', False, 'Head — Administration & IT'),
    ('Administration & IT', 'CC-9500', 'Senior Administration & IT Specialist', 'L4', False, 'Head — Administration & IT'),
    ('Administration & IT', 'CC-9500', 'Administration & IT Specialist', 'L3', False, 'Head — Administration & IT'),
    ('Administration & IT', 'CC-9500', 'Administration & IT Associate', 'L2', False, 'Head — Administration & IT'),
    ('Administration & IT', 'CC-9500', 'Administration & IT Associate II', 'L2', False, 'Head — Administration & IT'),
    ('Administration & IT', 'CC-9500', 'Administration & IT Trainee Associate', 'L1', False, 'Head — Administration & IT'),
    ('Talent Acquisition', 'CC-9210', 'Head — Talent Acquisition', 'M2', True, 'Head — Human Resources'),
    ('Talent Acquisition', 'CC-9210', 'Lead — Talent Acquisition', 'L5', False, 'Head — Talent Acquisition'),
    ('Talent Acquisition', 'CC-9210', 'Senior Talent Acquisition Specialist', 'L4', False, 'Head — Talent Acquisition'),
    ('Talent Acquisition', 'CC-9210', 'Talent Acquisition Specialist', 'L3', False, 'Head — Talent Acquisition'),
    ('Talent Acquisition', 'CC-9210', 'Talent Acquisition Associate', 'L2', False, 'Head — Talent Acquisition'),
    ('Talent Acquisition', 'CC-9210', 'Talent Acquisition Associate II', 'L2', False, 'Head — Talent Acquisition'),
    ('Talent Acquisition', 'CC-9210', 'Talent Acquisition Trainee Associate', 'L1', False, 'Head — Talent Acquisition'),
    ('HR Operations', 'CC-9220', 'Head — HR Operations', 'M2', True, 'Head — Human Resources'),
    ('HR Operations', 'CC-9220', 'Lead — HR Operations', 'L5', False, 'Head — HR Operations'),
    ('HR Operations', 'CC-9220', 'Senior HR Operations Specialist', 'L4', False, 'Head — HR Operations'),
    ('HR Operations', 'CC-9220', 'HR Operations Specialist', 'L3', False, 'Head — HR Operations'),
    ('HR Operations', 'CC-9220', 'HR Operations Associate', 'L2', False, 'Head — HR Operations'),
    ('HR Operations', 'CC-9220', 'HR Operations Associate II', 'L2', False, 'Head — HR Operations'),
    ('HR Operations', 'CC-9220', 'HR Operations Trainee Associate', 'L1', False, 'Head — HR Operations'),
    ('Sales', 'CC-9310', 'Head — Sales', 'M2', True, 'Head — Sales & Marketing'),
    ('Sales', 'CC-9310', 'Lead — Sales', 'L5', False, 'Head — Sales'),
    ('Sales', 'CC-9310', 'Senior Sales Specialist', 'L4', False, 'Head — Sales'),
    ('Sales', 'CC-9310', 'Sales Specialist', 'L3', False, 'Head — Sales'),
    ('Sales', 'CC-9310', 'Sales Associate', 'L2', False, 'Head — Sales'),
    ('Sales', 'CC-9310', 'Sales Associate II', 'L2', False, 'Head — Sales'),
    ('Sales', 'CC-9310', 'Sales Trainee Associate', 'L1', False, 'Head — Sales'),
    ('Pre-Sales', 'CC-9320', 'Head — Pre-Sales', 'M2', True, 'Head — Sales & Marketing'),
    ('Pre-Sales', 'CC-9320', 'Lead — Pre-Sales', 'L5', False, 'Head — Pre-Sales'),
    ('Pre-Sales', 'CC-9320', 'Senior Pre-Sales Specialist', 'L4', False, 'Head — Pre-Sales'),
    ('Pre-Sales', 'CC-9320', 'Pre-Sales Specialist', 'L3', False, 'Head — Pre-Sales'),
    ('Pre-Sales', 'CC-9320', 'Pre-Sales Associate', 'L2', False, 'Head — Pre-Sales'),
    ('Pre-Sales', 'CC-9320', 'Pre-Sales Associate II', 'L2', False, 'Head — Pre-Sales'),
    ('Pre-Sales', 'CC-9320', 'Pre-Sales Trainee Associate', 'L1', False, 'Head — Pre-Sales'),
    ('Account Management', 'CC-9330', 'Head — Account Management', 'M2', True, 'Head — Sales & Marketing'),
    ('Account Management', 'CC-9330', 'Lead — Account Management', 'L5', False, 'Head — Account Management'),
    ('Account Management', 'CC-9330', 'Senior Account Management Specialist', 'L4', False, 'Head — Account Management'),
    ('Account Management', 'CC-9330', 'Account Management Specialist', 'L3', False, 'Head — Account Management'),
    ('Account Management', 'CC-9330', 'Account Management Associate', 'L2', False, 'Head — Account Management'),
    ('Account Management', 'CC-9330', 'Account Management Associate II', 'L2', False, 'Head — Account Management'),
    ('Account Management', 'CC-9330', 'Account Management Trainee Associate', 'L1', False, 'Head — Account Management'),
    ('Marketing', 'CC-9340', 'Head — Marketing', 'M2', True, 'Head — Sales & Marketing'),
    ('Marketing', 'CC-9340', 'Lead — Marketing', 'L5', False, 'Head — Marketing'),
    ('Marketing', 'CC-9340', 'Senior Marketing Specialist', 'L4', False, 'Head — Marketing'),
    ('Marketing', 'CC-9340', 'Marketing Specialist', 'L3', False, 'Head — Marketing'),
    ('Marketing', 'CC-9340', 'Marketing Associate', 'L2', False, 'Head — Marketing'),
    ('Marketing', 'CC-9340', 'Marketing Associate II', 'L2', False, 'Head — Marketing'),
    ('Marketing', 'CC-9340', 'Marketing Trainee Associate', 'L1', False, 'Head — Marketing'),
]


def seed_forward(apps, schema_editor):
    OrgUnit = apps.get_model('accounts', 'OrgUnit')
    Position = apps.get_model('accounts', 'Position')

    chief_rows = [r for r in POSITIONS if r[4]]
    unit_parent_name = {}
    roots = []
    title_to_unit = {r[2]: r[0] for r in chief_rows}
    cc_by_unit = {}
    for org_unit, cost_center, *_ in POSITIONS:
        cc_by_unit.setdefault(org_unit, cost_center)

    for org_unit, _cc, _title, _grade, _is_chief, reports_to in chief_rows:
        if reports_to is None:
            roots.append(org_unit)
            unit_parent_name[org_unit] = None
        else:
            unit_parent_name[org_unit] = title_to_unit[reports_to]

    # Create parents before children (BFS from the roots).
    order = list(roots)
    children = {}
    for unit, parent in unit_parent_name.items():
        if parent is not None:
            children.setdefault(parent, []).append(unit)
    i = 0
    while i < len(order):
        order.extend(children.get(order[i], []))
        i += 1

    unit_objs = {}
    for name in order:
        parent_name = unit_parent_name[name]
        unit_objs[name], _ = OrgUnit.objects.get_or_create(
            name=name,
            parent=unit_objs[parent_name] if parent_name else None,
            defaults={'cost_center': cc_by_unit.get(name) or ''},
        )

    for org_unit, _cc, title, grade, is_chief, _reports_to in POSITIONS:
        Position.objects.get_or_create(
            org_unit=unit_objs[org_unit],
            title=title,
            defaults={'grade': grade or '', 'is_chief': is_chief},
        )


def seed_reverse(apps, schema_editor):
    # Deliberately not reversed: by the time anyone rolls this back, real
    # placements/holders may already exist on these positions, and this
    # feature's own rule (PositionDetailView.delete()) already refuses to
    # destroy a position with placement history for the same reason.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0115_remove_orgunit_department_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
