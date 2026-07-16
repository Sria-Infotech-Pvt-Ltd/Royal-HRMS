"use client";

interface DeptNode {
  id:            string;
  deptLabel:     string;
  headName:      string;
  headRole:      string;
  membersDisplay: string;
}

const ROOT = { role: "Managing Director", name: "Sunil Varghese" };

const DEPARTMENTS: DeptNode[] = [
  { id: "hr",  deptLabel: "HR",          headName: "Kavitha Rajan", headRole: "HR Admin",        membersDisplay: "–" },
  { id: "eng", deptLabel: "ENGINEERING", headName: "Arjun Mehta",   headRole: "Sr. Manager",     membersDisplay: "Priya Sharma, Suresh Kumar" },
  { id: "fin", deptLabel: "FINANCE",     headName: "Meena Iyer",    headRole: "Finance Manager", membersDisplay: "2 members" },
  { id: "it",  deptLabel: "IT",          headName: "Ravi Shankar",  headRole: "System Admin",    membersDisplay: "–" },
];

const LINE = "var(--outline-v)";
const DEPT_COLOR = "var(--secondary)";

interface DeptColProps {
  dept:    DeptNode;
  isFirst: boolean;
  isLast:  boolean;
}

function DeptCol({ dept, isFirst, isLast }: DeptColProps) {
  return (
    <div style={{
      flex: "1 0 160px",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      paddingTop: 28,
      paddingLeft: 10,
      paddingRight: 10,
      position: "relative",
    }}>
      {/* Horizontal bar segment connecting siblings */}
      <div style={{
        position: "absolute",
        top: 0,
        left:  isFirst ? "50%" : 0,
        right: isLast  ? "50%" : 0,
        height: 1,
        background: LINE,
      }} />

      {/* Vertical drop from bar to dept card */}
      <div style={{ width: 1, height: 28, background: LINE, flexShrink: 0 }} />

      {/* Dept head card */}
      <div style={{
        background: "#fff",
        border: "1px solid var(--outline-v)",
        borderRadius: "var(--radius-lg)",
        padding: "16px 18px",
        textAlign: "center",
        width: "100%",
        boxShadow: "var(--shadow)",
      }}>
        <div style={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.08em",
          color: DEPT_COLOR,
          textTransform: "uppercase",
          marginBottom: 8,
        }}>
          {dept.deptLabel}
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, color: "var(--on-bg)", marginBottom: 3 }}>
          {dept.headName}
        </div>
        <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
          {dept.headRole}
        </div>
      </div>

      {/* Vertical drop to team card */}
      <div style={{ width: 1, height: 18, background: LINE, flexShrink: 0 }} />

      {/* Team members card */}
      <div style={{
        background: "var(--bg-low)",
        border: "1px solid var(--outline-v)",
        borderRadius: "var(--radius-lg)",
        padding: "12px 16px",
        textAlign: "center",
        width: "100%",
      }}>
        <div style={{ fontSize: 11, color: "var(--on-variant)", marginBottom: 4 }}>
          Team members
        </div>
        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>
          {dept.membersDisplay}
        </div>
      </div>
    </div>
  );
}

export default function OrgChartClient() {
  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Organisation Chart</div>
          <div className="page-sub">Royal Staffing Services LLP</div>
        </div>
      </div>

      {/* Mobile hint — visible below sm breakpoint via injected style */}
      <div
        className="org-mobile-hint alert alert-info mb-16"
        style={{ display: "none" }}
        suppressHydrationWarning
      >
        <i className="ti ti-arrows-horizontal" /> Scroll horizontally to view the full chart.
      </div>

      <div className="card" style={{ padding: "32px 16px" }}>
        {/* Horizontally scrollable wrapper for small screens */}
        <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
          <div style={{ minWidth: 640, display: "flex", flexDirection: "column", alignItems: "center" }}>

            {/* Root node */}
            <div style={{
              background: "#fff",
              border: "1.5px solid var(--outline-v)",
              borderRadius: "var(--radius-lg)",
              padding: "16px 40px",
              textAlign: "center",
              boxShadow: "var(--shadow)",
            }}>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 6 }}>
                {ROOT.role}
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, color: "var(--on-bg)" }}>
                {ROOT.name}
              </div>
            </div>

            {/* Vertical line from root to children row */}
            <div style={{ width: 1, height: 28, background: LINE }} />

            {/* Department columns row */}
            <div style={{ display: "flex", width: "100%", alignItems: "flex-start" }}>
              {DEPARTMENTS.map((dept, i) => (
                <DeptCol
                  key={dept.id}
                  dept={dept}
                  isFirst={i === 0}
                  isLast={i === DEPARTMENTS.length - 1}
                />
              ))}
            </div>

          </div>
        </div>
      </div>

      {/* Mobile-only: vertical card list */}
      <style>{`
        @media (max-width: 639px) {
          .org-mobile-hint { display: flex !important; }
        }
      `}</style>
    </>
  );
}
