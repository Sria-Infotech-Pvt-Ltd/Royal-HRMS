"use client";

import CorrectionsTab from "./CorrectionsTab";

export default function UnpunchesTab() {
  return (
    <>
      <div className="alert alert-warn mb-16">
        <i className="ti ti-alert-triangle" />
        <span>
          Review and approve or reject attendance correction requests submitted by employees for missing punches.
        </span>
      </div>

      <CorrectionsTab />
    </>
  );
}
