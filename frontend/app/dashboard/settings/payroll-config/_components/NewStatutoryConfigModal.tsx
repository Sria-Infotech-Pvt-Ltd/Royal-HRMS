import { useRef } from "react";

interface StateOption { id: number; name: string; code: string; is_active: boolean; }

interface NewStatutoryConfigModalProps {
  availableStates: StateOption[];
  newStateId: string;
  setNewStateId: (id: string) => void;
  saving: boolean;
  onClose: () => void;
  onCreate: () => void;
}

export default function NewStatutoryConfigModal({
  availableStates, newStateId, setNewStateId, saving, onClose, onCreate,
}: NewStatutoryConfigModalProps) {
  // A click's target is resolved at mouseup, not mousedown — selecting text
  // inside a field and releasing past the modal's edge would otherwise land
  // on the overlay and close it mid-input. Only close when the gesture both
  // started AND ended on the backdrop itself.
  const mouseDownOnOverlay = useRef(false);

  return (
    <div
      className="fixed inset-0 z-[1000] bg-black/40 flex items-center justify-center p-4"
      onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onClick={e => mouseDownOnOverlay.current && e.target === e.currentTarget && onClose()}
    >
      <div className="bg-[var(--surface)] rounded-2xl w-full max-w-sm shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--outline-v)]">
          <div className="font-semibold text-[var(--on-bg)]">Add State Config</div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-[var(--outline)] hover:bg-[var(--bg-mid)]"><i className="ti ti-x" /></button>
        </div>
        <div className="px-6 py-5">
          <label className="block text-[12px] font-semibold text-[var(--on-bg)] mb-1.5">State</label>
          <select
            value={newStateId}
            onChange={e => setNewStateId(e.target.value)}
            className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)] field-select"
          >
            <option value="">Select a state</option>
            {availableStates.map(s => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}
          </select>
          <div className="flex items-center justify-end gap-2 mt-4">
            <button onClick={onClose} className="px-4 py-2 text-sm text-[var(--on-variant)] border border-[var(--outline-v)] rounded-lg hover:bg-[var(--bg-mid)]">Cancel</button>
            <button
              onClick={onCreate}
              disabled={saving || !newStateId}
              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-[var(--info)] text-white rounded-lg hover:bg-[var(--info)] disabled:opacity-50"
            >
              {saving ? "Creating…" : "Create Config"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
