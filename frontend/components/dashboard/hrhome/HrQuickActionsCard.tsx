"use client";

import styles from "./hrHome.module.css";
import { useT } from "@/hooks/useI18n";

export interface HrQuickAction {
  key: string;
  label: string;
  icon: string;
  onClick: () => void;
}

/** Only actions the person is allowed to use are passed in; nothing here grants access. */
export default function HrQuickActionsCard({ actions }: { actions: HrQuickAction[] }) {
  const t = useT();
  return (
    <section className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}><i className="ti ti-bolt" /> {t("Quick Actions")}</h2>
      </div>
      {actions.length === 0 && <div className={styles.emptyFill}>{t("No shortcuts are available for your role yet.")}</div>}
      <div className={styles.actions}>
        {actions.map(action => (
          <button key={action.key} type="button" className={styles.action} onClick={action.onClick}>
            <span className={styles.actionIcon}><i className={`ti ${action.icon}`} /></span>
            {t(action.label)}
          </button>
        ))}
      </div>
    </section>
  );
}
