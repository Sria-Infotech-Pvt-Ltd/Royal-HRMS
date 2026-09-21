// Deterministic natural-language-style query parser for the Employee
// Directory's "AI Assist" panel. Matches plain keywords against the real
// filter dimensions the table already supports (status/department/branch) —
// no external AI/LLM call, nothing fabricated. Anything left over after
// matching becomes a plain name/ID/email search, reusing the same search
// the toolbar's search box already does.

export type ParsedEmployeeStatus = "active" | "onboarding" | "probation" | "notice_period" | "inactive";

export interface EmployeeQueryOptions {
  departments: string[];
  branches: string[];
}

export interface ParsedEmployeeQuery {
  status: ParsedEmployeeStatus | null;
  department: string | null;
  branch: string | null;
  search: string;
  matched: string[]; // human-readable summary of what was detected
}

const STATUS_KEYWORDS: { status: ParsedEmployeeStatus; words: string[] }[] = [
  { status: "notice_period", words: ["notice period", "serving notice", "resigning", "exiting"] },
  { status: "probation", words: ["probation", "on probation"] },
  { status: "onboarding", words: ["onboarding", "new joiner", "new joiners"] },
  { status: "inactive", words: ["inactive", "deactivated", "former", "exited"] },
  { status: "active", words: ["active", "current employees", "currently employed"] },
];

function stripMatched(text: string, phrase: string): string {
  const re = new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "ig");
  return text.replace(re, " ");
}

export function parseEmployeeQuery(rawQuery: string, options: EmployeeQueryOptions): ParsedEmployeeQuery {
  let remaining = rawQuery.trim();
  const lower = remaining.toLowerCase();
  const matched: string[] = [];

  let status: ParsedEmployeeStatus | null = null;
  for (const { status: candidate, words } of STATUS_KEYWORDS) {
    const hit = words.find(w => lower.includes(w));
    if (hit) {
      status = candidate;
      matched.push(`Status: ${candidate}`);
      remaining = stripMatched(remaining, hit);
      break;
    }
  }

  // Longest match first, so "AI & ML" wins over a shorter unrelated substring.
  let department: string | null = null;
  for (const dept of [...options.departments].sort((a, b) => b.length - a.length)) {
    if (dept && remaining.toLowerCase().includes(dept.toLowerCase())) {
      department = dept;
      matched.push(`Org unit: ${dept}`);
      remaining = stripMatched(remaining, dept);
      break;
    }
  }

  let branch: string | null = null;
  for (const b of [...options.branches].sort((a, b2) => b2.length - a.length)) {
    if (b && remaining.toLowerCase().includes(b.toLowerCase())) {
      branch = b;
      matched.push(`Location: ${b}`);
      remaining = stripMatched(remaining, b);
      break;
    }
  }

  // Drop connector words left behind once status/department/branch are
  // stripped out, so leftover text used as a name/ID/email search doesn't
  // start with "employees in at".
  const STOPWORDS = new Set(["employees", "employee", "in", "at", "for", "with", "and", "the", "who", "are", "of"]);
  const search = remaining
    .split(/\s+/)
    .filter(w => w && !STOPWORDS.has(w.toLowerCase()))
    .join(" ")
    .trim();

  if (search) matched.push(`Search: "${search}"`);

  return { status, department, branch, search, matched };
}
