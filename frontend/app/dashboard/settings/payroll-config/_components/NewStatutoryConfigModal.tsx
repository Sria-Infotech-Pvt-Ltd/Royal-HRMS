import Modal from "@/components/Modal";
import { useT } from "@/hooks/useI18n";

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
  const t = useT();
  return (
    <Modal
      title={<><i className="ti ti-building-bank" style={{ marginRight: 8, color: "var(--primary)" }} />{t("Add State Configuration")}</>}
      onClose={onClose}
      maxWidth={480}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>{t("Cancel")}</button>
          <button className="btn btn-filled" onClick={onCreate} disabled={saving || !newStateId}>
            {saving ? t("Creating…") : t("Create Config")}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm leading-relaxed -mt-1" style={{ color: "var(--on-variant)" }}>
          {t("Choose a state to configure its professional tax, employee state insurance, and labour welfare fund settings.")}
        </p>
        <label htmlFor="statutory-state" className="block text-[12px] font-semibold text-[var(--on-bg)]">
          {t("State")} <span className="text-[var(--error)]">*</span>
        </label>
        <select
          id="statutory-state"
          autoFocus
          value={newStateId}
          onChange={e => setNewStateId(e.target.value)}
          className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)] field-select"
        >
          <option value="">{t("Select a state")}</option>
          {availableStates.map(s => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}
        </select>
      </div>
    </Modal>
  );
}
