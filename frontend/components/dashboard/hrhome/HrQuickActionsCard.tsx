"use client";

import styles from "./hrHome.module.css";

export interface HrQuickAction {
  key: string;
  label: string;
  icon: string;
  onClick: () => void;
}

/** Only actions the person is allowed to use are passed in; nothing here grants access. */
export default function HrQuickActionsCard({ actions }: { actions: HrQuickAction[] }) {
  return (
    <section className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}><i className="ti ti-bolt" /> Quick Actions</h2>
      </div>
      {actions.length === 0 && <div className={styles.emptyFill}>No shortcuts are available for your role yet.</div>}
      <div className={styles.actions}>
        {actions.map(action => (
          <button key={action.key} type="button" className={styles.action} onClick={action.onClick}>
            <span className={styles.actionIcon}><i className={`ti ${action.icon}`} /></span>
            {action.label}
          </button>
        ))}
      </div>
    </section>
  );
}
