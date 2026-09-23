export interface PTSlab { min: number; max: number | null; amount: number; }

interface PtSlabsEditorProps {
  slabs: PTSlab[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  onUpdate: (index: number, field: keyof PTSlab, raw: string) => void;
}

export default function PtSlabsEditor({ slabs, onAdd, onRemove, onUpdate }: PtSlabsEditorProps) {
  return (
    <div className="mt-4">
      <div className="text-[11px] font-bold text-[var(--on-variant)] uppercase tracking-wider mb-2">PT Slabs</div>
      <div className="border border-[var(--outline-v)] rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--bg-mid)] border-b border-[var(--outline-v)]">
              <th className="px-3 py-2 text-left text-[11px] font-semibold text-[var(--on-variant)] uppercase">Min (₹)</th>
              <th className="px-3 py-2 text-left text-[11px] font-semibold text-[var(--on-variant)] uppercase">Max (₹)</th>
              <th className="px-3 py-2 text-left text-[11px] font-semibold text-[var(--on-variant)] uppercase">PT Amount (₹/mo)</th>
              <th className="px-3 py-2 w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--outline-v)]">
            {slabs.map((slab, i) => (
              <tr key={i}>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    min={0}
                    value={slab.min}
                    onChange={e => onUpdate(i, "min", e.target.value)}
                    className="w-full rounded border border-[var(--outline-v)] px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)]"
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    min={0}
                    value={slab.max ?? ""}
                    placeholder="No limit"
                    onChange={e => onUpdate(i, "max", e.target.value)}
                    className="w-full rounded border border-[var(--outline-v)] px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)]"
                  />
                </td>
                <td className="px-3 py-2">
                  <input
                    type="number"
                    min={0}
                    value={slab.amount}
                    onChange={e => onUpdate(i, "amount", e.target.value)}
                    className="w-full rounded border border-[var(--outline-v)] px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)]"
                  />
                </td>
                <td className="px-3 py-2 text-right">
                  <button
                    onClick={() => onRemove(i)}
                    className="text-[var(--error)] hover:text-[var(--error)] transition-colors p-1 rounded"
                    title="Remove slab"
                  >
                    <i className="ti ti-trash text-sm" />
                  </button>
                </td>
              </tr>
            ))}
            {slabs.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-center text-[var(--outline)] text-xs">
                  No PT slabs defined — add one below
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <button
        onClick={onAdd}
        className="mt-2 flex items-center gap-1.5 text-[12px] text-[var(--info)] border border-[var(--info)] hover:bg-[var(--info-c)] px-3 py-1.5 rounded-lg transition-colors"
      >
        <i className="ti ti-plus text-xs" /> Add Slab
      </button>
      <div className="mt-2 text-[11px] text-[var(--outline)]">
        Leave Max blank on the last slab to apply it to all higher incomes.
      </div>
    </div>
  );
}
