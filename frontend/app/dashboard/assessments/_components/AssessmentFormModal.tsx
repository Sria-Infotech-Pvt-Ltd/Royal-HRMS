"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import {
  attemptsForMode, attemptsMode, buildAssessmentPayload, describeAttempts, describeTime, hasErrors, rulesSummary,
  timeForMode, timeMode, validateAssessmentForm, type AttemptsMode, type GlobalDefaults, type TimeMode,
} from "@/lib/assessmentForm";
import type { AssessmentForm } from "../_types";
import { useT } from "@/hooks/useI18n";

interface AssessmentFormModalProps {
  isEditing: boolean
  form:      AssessmentForm
  onChange:  (next: AssessmentForm) => void
  /** Error from the server after a save attempt. */
  serverError: string
  isSaving:  boolean
  defaults:  GlobalDefaults
  onSave:    (payload: ReturnType<typeof buildAssessmentPayload>) => void
  onClose:   () => void
}

interface Choice<Value extends string> { value: Value; label: string; hint?: string }

function Segmented<Value extends string>({ label, choices, value, onPick }: { label: string; choices: Choice<Value>[]; value: Value; onPick: (value: Value) => void }) {
  const t = useT();
  return (
    <div className="asmf-seg" role="radiogroup" aria-label={t(label)}>
      {choices.map(choice => (
        <button key={choice.value} type="button" role="radio" aria-checked={choice.value === value}
          className={choice.value === value ? "on" : ""} onClick={() => onPick(choice.value)}>
          {t(choice.label)}
        </button>
      ))}
    </div>
  );
}

function Section({ icon, title, hint, children }: { icon: string; title: string; hint?: string; children: React.ReactNode }) {
  const t = useT();
  return (
    <section className="asmf-section">
      <header><span className="asmf-section-icon"><i className={`ti ${icon}`} /></span><div><h4>{t(title)}</h4>{hint && <p>{hint}</p>}</div></header>
      {children}
    </section>
  );
}

const ATTEMPT_CHOICES: Choice<AttemptsMode>[] = [
  { value: "global", label: "Use global" }, { value: "unlimited", label: "Unlimited" }, { value: "limited", label: "Set a limit" },
];
const TIME_CHOICES: Choice<TimeMode>[] = [{ value: "global", label: "Use global" }, { value: "limited", label: "Set a limit" }];

/** Create or edit an assessment: basics, pass mark, attempts, time limit and whether it is active, with a live summary. */
export default function AssessmentFormModal(props: AssessmentFormModalProps) {
  const t = useT();
  const { form, defaults, isSaving } = props;
  const [showErrors, setShowErrors] = useState(false);
  const errors = validateAssessmentForm(form);
  const shown = showErrors ? errors : {};
  const set = (patch: Partial<AssessmentForm>) => props.onChange({ ...form, ...patch });

  function save() {
    setShowErrors(true);
    if (!hasErrors(errors)) props.onSave(buildAssessmentPayload(form));
  }

  const pass = Math.min(100, Math.max(1, Number(form.pass_percentage) || 1));

  return (
    <Modal
      title={props.isEditing ? t("Edit assessment") : t("New assessment")}
      onClose={props.onClose}
      closeDisabled={isSaving}
      maxWidth={640}
      scrollBody
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={props.onClose} disabled={isSaving}>{t("Cancel")}</button>
          <button type="button" className="btn btn-filled" onClick={save} disabled={isSaving}>
            {isSaving ? <><i className="ti ti-loader-2 spin" /> {t("Saving…")}</> : <><i className="ti ti-check" /> {props.isEditing ? t("Save changes") : t("Create assessment")}</>}
          </button>
        </>
      }
    >
      {props.serverError && <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{props.serverError}</div></div>}

      <Section icon="ti-file-text" title={t("Basics")} hint={t("What people will see when they are assigned this assessment.")}>
        <div className="field-group">
          <label className="field-label" htmlFor="asmf-title">{t("Title *")}</label>
          <input id="asmf-title" className={`field-input${shown.title ? " has-error" : ""}`} value={form.title} placeholder={t("e.g. Onboarding Assessment")}
            aria-invalid={!!shown.title} onChange={event => set({ title: event.target.value })} autoFocus />
          {shown.title && <div className="asmf-error">{t(shown.title)}</div>}
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="asmf-desc">{t("Description")}</label>
          <textarea id="asmf-desc" className="field-input" rows={2} value={form.description} placeholder={t("What does this assessment cover?")}
            onChange={event => set({ description: event.target.value })} />
        </div>
      </Section>

      <Section icon="ti-target" title={t("Pass mark")} hint={t("The score a person needs to pass.")}>
        <div className="asmf-pass">
          <input type="range" min={1} max={100} value={pass} aria-label={t("Pass mark slider")} onChange={event => set({ pass_percentage: event.target.value })} />
          <div className="asmf-pass-box">
            <input type="number" min={1} max={100} className={`field-input${shown.pass ? " has-error" : ""}`} value={form.pass_percentage}
              aria-label={t("Pass percentage")} aria-invalid={!!shown.pass} onChange={event => set({ pass_percentage: event.target.value })} />
            <span>%</span>
          </div>
        </div>
        {shown.pass && <div className="asmf-error">{t(shown.pass)}</div>}
      </Section>

      <div className="asmf-stack">
        <Section icon="ti-refresh" title={t("Attempts")} hint={t("Global setting: {value}.", { value: describeAttempts(defaults.maxAttempts) })}>
          <Segmented label={t("Attempts")} choices={ATTEMPT_CHOICES} value={attemptsMode(form.max_attempts)}
            onPick={mode => set({ max_attempts: attemptsForMode(mode, form.max_attempts) })} />
          {attemptsMode(form.max_attempts) === "limited" && (
            <div className="asmf-inline">
              <input type="number" min={1} className={`field-input${shown.attempts ? " has-error" : ""}`} value={form.max_attempts}
                aria-label={t("Number of attempts")} onChange={event => set({ max_attempts: event.target.value })} />
              <span>{t("attempts")}</span>
            </div>
          )}
          {shown.attempts && <div className="asmf-error">{t(shown.attempts)}</div>}
        </Section>

        <Section icon="ti-clock" title={t("Time limit")} hint={t("Global setting: {value}.", { value: describeTime(defaults.timeLimitMins) })}>
          <Segmented label={t("Time limit")} choices={TIME_CHOICES} value={timeMode(form.time_limit_mins)}
            onPick={mode => set({ time_limit_mins: timeForMode(mode, form.time_limit_mins, defaults.timeLimitMins) })} />
          {timeMode(form.time_limit_mins) === "limited" && (
            <div className="asmf-inline">
              <input type="number" min={1} className={`field-input${shown.time ? " has-error" : ""}`} value={form.time_limit_mins}
                aria-label={t("Time limit in minutes")} onChange={event => set({ time_limit_mins: event.target.value })} />
              <span>{t("minutes")}</span>
            </div>
          )}
          {shown.time && <div className="asmf-error">{t(shown.time)}</div>}
        </Section>
      </div>

      <label className="asmf-switch">
        <input type="checkbox" role="switch" checked={form.is_active} onChange={event => set({ is_active: event.target.checked })} />
        <span className="asmf-switch-track" aria-hidden="true" />
        <span className="asmf-switch-text">
          <strong>{form.is_active ? t("Active") : t("Inactive")}</strong>
          <small>{form.is_active ? t("Shown as Active in the assessment list.") : t("Shown as Inactive in the assessment list.")}</small>
        </span>
      </label>

      <div className="asmf-summary" aria-live="polite">
        <span className="asmf-summary-label"><i className="ti ti-list-check" /> {t("How it will work")}</span>
        {rulesSummary(form, defaults).map(part => <span key={part}>{t(part)}</span>)}
      </div>
    </Modal>
  );
}
