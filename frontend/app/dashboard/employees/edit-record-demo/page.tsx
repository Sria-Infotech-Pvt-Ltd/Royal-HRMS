"use client";

// Preview-only route for the pixel-faithful "Edit record" mock
// (EditRecordModalMock.tsx) — mock/placeholder data only, no API calls.
// Not linked from anywhere in the real navigation; visit directly at
// /dashboard/employees/edit-record-demo to view it.

import { useState } from "react";
import { useRouter } from "next/navigation";
import EditRecordModalMock from "../_components/EditRecordModalMock";

export default function EditRecordDemoPage() {
  const router = useRouter();
  const [open, setOpen] = useState(true);

  return (
    <div className="p-10">
      <h1 className="text-lg font-semibold mb-2">Edit record — mock preview</h1>
      <p className="text-sm text-slate-500 mb-4">
        Mock/placeholder data only. Reopen with the button below if closed.
      </p>
      <button
        onClick={() => setOpen(true)}
        className="px-4 py-2 rounded-lg text-white text-sm font-semibold"
        style={{ background: "#6D28D9" }}
      >
        Open Edit record
      </button>
      {open && <EditRecordModalMock onClose={() => { setOpen(false); router.back(); }} />}
    </div>
  );
}
