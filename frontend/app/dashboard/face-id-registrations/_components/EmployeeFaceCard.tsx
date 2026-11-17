"use client";

import Link from "next/link";
import { formatDate } from "@/lib/formatDate";
import { FACE_STATE_META, actionLabel, faceStateOf, personInitials, stateDetails } from "@/lib/faceRegistrationStatus";
import type { FaceRegistrationEmployee, FaceRegistrationRequest } from "@/types/faceRegistration";

interface EmployeeFaceCardProps {
  employee:        FaceRegistrationEmployee | null
  status:          Partial<FaceRegistrationRequest> | null | undefined
  isLoading:       boolean
  error:           string | null
  isConfirming:    boolean
  onRegister:      () => void
  onConfirm:       () => void
  onCancelConfirm: () => void
  /** Step 1: take the person to the employee search. */
  onStart:         () => void
}

const STEPS = [
  { icon: "ti-user-search",  title: "Pick an employee", text: "Search the list and choose who is with you.",                          isOpen: true },
  { icon: "ti-shield-check", title: "Get their consent", text: "They read and agree to the notice before the camera opens.",           isOpen: false },
  { icon: "ti-camera",       title: "Capture the face",  text: "A short blink and head-turn check, then it is saved and approved.",    isOpen: false },
];

function EmptyDetail({ onStart }: { onStart: () => void }) {
  return (
    <div className="card fid-detail fid-detail-empty">
      <i className="ti ti-face-id fid-empty-icon" />
      <h3>Select an employee</h3>
      <p>Choose someone from the list to see their Face ID status or register it in person.</p>
      <ol className="fid-steps">
        {STEPS.map((step, index) => (
          <li key={step.title}>
            <button
              type="button"
              className={`fid-step${step.isOpen ? " is-open" : " is-locked"}`}
              onClick={onStart}
              aria-label={step.isOpen ? `Step ${index + 1}: ${step.title}. Go to the employee search` : `Step ${index + 1}: ${step.title}. Locked until an employee is chosen`}
              title={step.isOpen ? "Go to the employee search" : "Choose an employee first"}
            >
              <span className="fid-step-no">{index + 1}</span>
              <i className={`ti ${step.icon}`} />
              <strong>{step.title}</strong>
              <span>{step.text}</span>
              <span className="fid-step-tag">
                {step.isOpen ? <>Start here <i className="ti ti-arrow-right" /></> : <><i className="ti ti-lock" /> Choose an employee first</>}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** The chosen employee: who they are, their Face ID status in plain words, and the register / update action. */
export default function EmployeeFaceCard(props: EmployeeFaceCardProps) {
  const { employee, status, isLoading, error, isConfirming } = props;
  if (!employee) return <EmptyDetail onStart={props.onStart} />;

  const state = faceStateOf(status?.status);
  const meta = FACE_STATE_META[state];
  const details = stateDetails(state, status, formatDate);
  const facts = [
    { icon: "ti-id", text: employee.employee_id },
    { icon: "ti-briefcase", text: employee.designation },
    { icon: "ti-building", text: employee.department },
    { icon: "ti-map-pin", text: employee.branch },
    { icon: "ti-mail", text: employee.email },
  ].filter(fact => fact.text);

  return (
    <div className="card fid-detail">
      <div className="fid-profile">
        <span className="fid-avatar lg" aria-hidden="true">{personInitials(employee.full_name)}</span>
        <div>
          <h3>{employee.full_name}</h3>
          <ul className="fid-facts">
            {facts.map(fact => <li key={fact.icon}><i className={`ti ${fact.icon}`} /> {fact.text}</li>)}
          </ul>
        </div>
      </div>

      {error && <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{error}</div></div>}

      {isLoading ? (
        <div className="fid-state is-loading" role="status" aria-label="Loading Face ID status"><span className="cand-skeleton-bar" /></div>
      ) : (
        <div className={`fid-state tone-${meta.tone}`}>
          <span className="fid-state-icon"><i className={`ti ${meta.icon}`} /></span>
          <div className="fid-state-text">
            <div className="fid-state-top"><strong>{meta.headline}</strong><span className={`badge ${meta.badge}`}>{meta.label}</span></div>
            {details.map(line => <p key={line}>{line}</p>)}
            {state === "none" && <p>This employee has not registered a Face ID. You can register it now, in person.</p>}
          </div>
        </div>
      )}

      {isConfirming ? (
        <div className="fid-confirm" role="alertdialog" aria-label="Replace Face ID">
          <i className="ti ti-alert-triangle" />
          <div>
            <strong>Replace the current Face ID?</strong>
            <p>This will replace {employee.full_name}&apos;s registered Face ID will be replaced by the new capture.</p>
          </div>
          <div className="fid-confirm-buttons">
            <button type="button" className="btn btn-ghost btn-sm" onClick={props.onCancelConfirm}>Cancel</button>
            <button type="button" className="btn btn-filled btn-sm" onClick={props.onConfirm}>Replace</button>
          </div>
        </div>
      ) : (
        <div className="fid-actions">
          <button type="button" className="btn btn-filled" onClick={props.onRegister} disabled={isLoading}>
            <i className="ti ti-camera" /> {actionLabel(state)}
          </button>
          {state === "pending" && (
            <Link className="btn btn-ghost" href="/dashboard/approvals"><i className="ti ti-checklist" /> Review pending requests</Link>
          )}
          <span className="fid-note"><i className="ti ti-info-circle" /> Captured in person, so it is approved immediately.</span>
        </div>
      )}
    </div>
  );
}
