"use client";

import { forwardRef } from "react";
import type { StepIssue } from "@/lib/hireValidation";

interface StepIssuesPanelProps {
  /** Everything wrong on this step, as the person tries to leave it. */
  issues: StepIssue[]
  /** A message from the server (a save that failed, a duplicate email) that is not tied to one field. */
  serverMessage: string
  /** A save-in-the-background problem: shown as a real notice, not as small grey text. */
  autosaveProblem: string
  onRetryAutosave: () => void
  /** Jump to a field: scroll it into view and put the cursor in it. */
  onGoToField: (field: string) => void
}

/**
 * Stays at the top of the step while the person scrolls, so what is wrong is never out of sight. Lists every problem at once; clicking
 * one takes you to that field.
 */
const StepIssuesPanel = forwardRef<HTMLDivElement, StepIssuesPanelProps>(function StepIssuesPanel(props, ref) {
  const { issues, serverMessage, autosaveProblem } = props;
  if (issues.length === 0 && !serverMessage && !autosaveProblem) return null;
  return (
    <div ref={ref} className="hw-issues" role="alert" aria-live="assertive">
      {serverMessage && (
        <div className="hw-issue-block is-error">
          <i className="ti ti-alert-circle" />
          <div><strong>This step could not be saved</strong><p>{serverMessage}</p></div>
        </div>
      )}
      {issues.length > 0 && (
        <div className="hw-issue-block is-error">
          <i className="ti ti-alert-circle" />
          <div>
            <strong>{issues.length === 1 ? "1 thing needs fixing before you can continue" : `${issues.length} things need fixing before you can continue`}</strong>
            <ul>
              {issues.map(issue => (
                <li key={`${issue.field}-${issue.message}`}>
                  <button type="button" onClick={() => props.onGoToField(issue.field)}>{issue.message}</button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      {autosaveProblem && (
        <div className="hw-issue-block is-warn">
          <i className="ti ti-cloud-off" />
          <div><strong>Your latest changes may not be saved</strong><p>{autosaveProblem}</p></div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={props.onRetryAutosave}>Retry</button>
        </div>
      )}
    </div>
  );
});

export default StepIssuesPanel;
