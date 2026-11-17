"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { usePermission } from "@/hooks/usePermission";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useFaceVerificationStatus } from "@/hooks/useFaceVerificationStatus";
import { useFaceRegistrationEmployeePicker, useEmployeeFaceStatus } from "@/hooks/useHRFaceRegistration";
import { faceStateOf, needsReplaceConfirmation } from "@/lib/faceRegistrationStatus";
import type { FaceRegistrationEmployee, FaceRosterFilter } from "@/types/faceRegistration";
import FaceIdHeader from "./_components/FaceIdHeader";
import EmployeePickerPanel from "./_components/EmployeePickerPanel";
import EmployeeFaceCard from "./_components/EmployeeFaceCard";
import FaceCoverageCard from "./_components/FaceCoverageCard";
import HRFaceCaptureModal from "./_components/HRFaceCaptureModal";

const SEARCH_DELAY_MS = 300;

export default function FaceIdRegistrationsPage() {
  const router = useRouter();
  const canRegister = usePermission("facial_recognition.approve");
  const faceStatus = useFaceVerificationStatus();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [faceFilter, setFaceFilter] = useState<FaceRosterFilter>("");
  const [selected, setSelected] = useState<FaceRegistrationEmployee | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [showCapture, setShowCapture] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const debouncedSearch = useDebouncedValue(search.trim(), SEARCH_DELAY_MS);
  const picker = useFaceRegistrationEmployeePicker(debouncedSearch, page, faceFilter);
  const { status, loading: isLoadingStatus, error: statusError, refetch: refetchStatus } = useEmployeeFaceStatus(selected?.uuid ?? null);

  if (!canRegister) {
    return (
      <div className="empty-state">
        <i className="ti ti-lock" />
        <h3>You don&apos;t have permission to manage face ID registrations</h3>
        <p>Contact an HR administrator if you believe this is a mistake.</p>
      </div>
    );
  }

  const state = faceStateOf(status?.status);
  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push("/dashboard");
  };

  // Step 1 of the guide: bring the employee search into view and put the cursor in it.
  function startPicking() {
    searchRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    searchRef.current?.focus({ preventScroll: true });
  }
  function changeSearch(text: string) { setSearch(text); setPage(1); }
  function changeFilter(next: FaceRosterFilter) { setFaceFilter(next); setPage(1); }
  function selectEmployee(employee: FaceRegistrationEmployee) { setSelected(employee); setIsConfirming(false); }
  function handleRegister() {
    if (needsReplaceConfirmation(state)) { setIsConfirming(true); return; }
    setShowCapture(true);
  }

  return (
    <div className="cand-page">
      <FaceIdHeader note={faceStatus.hrNote} onBack={goBack} />

      <FaceCoverageCard counts={picker.counts} isLoading={picker.loading && picker.total === 0 && picker.counts.total === 0} filter={faceFilter} onFilter={changeFilter} />

      <div className="fid-layout">
        <EmployeePickerPanel
          search={search} onSearch={changeSearch}
          employees={picker.employees} total={picker.total} page={picker.page} pageSize={picker.pageSize} totalPages={picker.totalPages}
          onPage={setPage} isLoading={picker.loading} error={picker.error}
          selectedId={selected?.uuid ?? null} onSelect={selectEmployee} filter={faceFilter} searchRef={searchRef}
        />
        <EmployeeFaceCard
          employee={selected} status={status} isLoading={isLoadingStatus} error={statusError}
          isConfirming={isConfirming} onRegister={handleRegister}
          onConfirm={() => { setIsConfirming(false); setShowCapture(true); }} onCancelConfirm={() => setIsConfirming(false)} onStart={startPicking}
        />
      </div>

      {showCapture && selected && (
        <HRFaceCaptureModal
          employeeUuid={selected.uuid}
          employeeName={selected.full_name}
          isUpdate={state === "approved"}
          onClose={() => setShowCapture(false)}
          onRegistered={() => { refetchStatus(); picker.refetch(); }}
        />
      )}
    </div>
  );
}
