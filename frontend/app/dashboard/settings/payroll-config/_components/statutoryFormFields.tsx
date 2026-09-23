export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="px-5 py-4">
      <div className="text-[11px] font-bold text-[var(--on-variant)] uppercase tracking-wider mb-3">{title}</div>
      {children}
    </div>
  );
}

export function ToggleRow({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[13px] font-medium text-[var(--on-bg)]">{label}</span>
      <button
        onClick={() => onChange(!value)}
        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${value ? "bg-[var(--info)]" : "bg-[var(--bg-mid)]"}`}
      >
        <span className={`inline-block h-3.5 w-3.5 rounded-full bg-[var(--surface)] shadow transition-transform ${value ? "translate-x-4" : "translate-x-0.5"}`} />
      </button>
    </div>
  );
}

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export function MonthSelect({
  label, value, onChange, disabledMonth,
}: {
  label: string;
  value: number | undefined;
  onChange: (month: number | undefined) => void;
  disabledMonth?: number;
}) {
  return (
    <div>
      <label className="block text-[12px] font-semibold text-[var(--on-bg)] mb-1">{label}</label>
      <select
        value={value ?? ""}
        onChange={e => onChange(e.target.value ? Number(e.target.value) : undefined)}
        className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)] field-select"
      >
        <option value="">Select month</option>
        {MONTH_NAMES.map((name, i) => (
          <option key={name} value={i + 1} disabled={disabledMonth === i + 1}>{name}</option>
        ))}
      </select>
    </div>
  );
}

export function NumField({ label, value, onChange, step }: { label: string; value: string; onChange: (v: string) => void; step?: string }) {
  return (
    <div>
      <label className="block text-[12px] font-semibold text-[var(--on-bg)] mb-1">{label}</label>
      <input
        type="number"
        step={step ?? "1"}
        min={0}
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)]"
      />
    </div>
  );
}
