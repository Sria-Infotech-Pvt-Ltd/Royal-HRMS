"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import {
  attemptsForMode, attemptsMode, buildAssessmentPayload, describeAttempts, describeTime, hasErrors, rulesSummary,
  timeForMode, timeMode, validateAssessmentForm, type AttemptsMode, type GlobalDefaults, type TimeMode,
} from "@/lib/assessmentForm";
import type { AssessmentForm } from "../_types";

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
  return (
    <div className="asmf-seg" role="radiogroup" aria-label={label}>
      {choices.map(choice => (
        <button key={choice.value} type="button" role="radio" aria-checked={choice.value === value}
          className={choice.value === value ? "on" : ""} onClick={() => onPick(choice.value)}>
          {choice.label}
        </button>
      ))}
    </div>
  );
}

function Section({ icon, title, hint, children }: { icon: string; title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="asmf-section">
      <header><span className="asmf-section-icon"><i className={`ti ${icon}`} /></span><div><h4>{title}</h4>{hint && <p>{hint}</p>}</div></header>
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
      title={props.isEditing ? "Edit assessment" : "New assessment"}
      onClose={props.onClose}
      closeDisabled={isSaving}
      maxWidth={640}
      scrollBody
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={props.onClose} disabled={isSaving}>Cancel</button>
          <button type="button" className="btn btn-filled" onClick={save} disabled={isSaving}>
            {isSaving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : <><i className="ti ti-check" /> {props.isEditing ? "Save changes" : "Create assessment"}</>}
          </button>
        </>
      }
    >
      {props.serverError && <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{props.serverError}</div></div>}

      <Section icon="ti-file-text" title="Basics" hint="What people will see when they are assigned this assessment.">
        <div className="field-group">
          <label className="field-label" htmlFor="asmf-title">Title *</label>
          <input id="asmf-title" className={`field-input${shown.title ? " has-error" : ""}`} value={form.title} placeholder="e.g. Onboarding Assessment"
            aria-invalid={!!shown.title} onChange={event => set({ title: event.target.value })} autoFocus />
          {shown.title && <div className="asmf-error">{shown.title}</div>}
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="asmf-desc">Description</label>
          <textarea id="asmf-desc" className="field-input" rows={2} value={form.description} placeholder="What does this assessment cover?"
            onChange={event => set({ description: event.target.value })} />
        </div>
      </Section>

      <Section icon="ti-target" title="Pass mark" hint="The score a person needs to pass.">
        <div className="asmf-pass">
          <input type="range" min={1} max={100} value={pass} aria-label="Pass mark slider" onChange={event => set({ pass_percentage: event.target.value })} />
          <div className="asmf-pass-box">
            <input type="number" min={1} max={100} className={`field-input${shown.pass ? " has-error" : ""}`} value={form.pass_percentage}
              aria-label="Pass percentage" aria-invalid={!!shown.pass} onChange={event => set({ pass_percentage: event.target.value })} />
            <span>%</span>
          </div>
        </div>
        {shown.pass && <div className="asmf-error">{shown.pass}</div>}
      </Section>

      <div className="asmf-stack">
        <Section icon="ti-refresh" title="Attempts" hint={`Global setting: ${describeAttempts(defaults.maxAttempts)}.`}>
          <Segmented label="Attempts" choices={ATTEMPT_CHOICES} value={attemptsMode(form.max_attempts)}
            onPick={mode => set({ max_attempts: attemptsForMode(mode, form.max_attempts) })} />
          {attemptsMode(form.max_attempts) === "limited" && (
            <div className="asmf-inline">
              <input type="number" min={1} className={`field-input${shown.attempts ? " has-error" : ""}`} value={form.max_attempts}
                aria-label="Number of attempts" onChange={event => set({ max_attempts: event.target.value })} />
              <span>attempts</span>
            </div>
          )}
          {shown.attempts && <div className="asmf-error">{shown.attempts}</div>}
        </Section>

        <Section icon="ti-clock" title="Time limit" hint={`Global setting: ${describeTime(defaults.timeLimitMins)}.`}>
          <Segmented label="Time limit" choices={TIME_CHOICES} value={timeMode(form.time_limit_mins)}
            onPick={mode => set({ time_limit_mins: timeForMode(mode, form.time_limit_mins, defaults.timeLimitMins) })} />
          {timeMode(form.time_limit_mins) === "limited" && (
            <div className="asmf-inline">
              <input type="number" min={1} className={`field-input${shown.time ? " has-error" : ""}`} value={form.time_limit_mins}
                aria-label="Time limit in minutes" onChange={event => set({ time_limit_mins: event.target.value })} />
              <span>minutes</span>
            </div>
          )}
          {shown.time && <div className="asmf-error">{shown.time}</div>}
        </Section>
      </div>

      <label className="asmf-switch">
        <input type="checkbox" role="switch" checked={form.is_active} onChange={event => set({ is_active: event.target.checked })} />
        <span className="asmf-switch-track" aria-hidden="true" />
        <span className="asmf-switch-text">
          <strong>{form.is_active ? "Active" : "Inactive"}</strong>
          <small>{form.is_active ? "Shown as Active in the assessment list." : "Shown as Inactive in the assessment list."}</small>
        </span>
      </label>

      <div className="asmf-summary" aria-live="polite">
        <span className="asmf-summary-label"><i className="ti ti-list-check" /> How it will work</span>
        {rulesSummary(form, defaults).map(part => <span key={part}>{part}</span>)}
      </div>
    </Modal>
  );
}
