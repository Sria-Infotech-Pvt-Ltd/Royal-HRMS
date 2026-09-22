"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { usePermission } from "@/hooks/usePermission";
import { useEmployees } from "@/hooks/useEmployees";
import Pagination from "@/components/shared/Pagination";
import type { Employee, EmployeeStatusFilter } from "./_data";
import EmployeeDirectoryHeader from "./_components/EmployeeDirectoryHeader";
import EmployeeStatCards from "./_components/EmployeeStatCards";
import EmployeeToolbar from "./_components/EmployeeToolbar";
import EmployeeTable from "./_components/EmployeeTable";
import AiAssistPanel from "./_components/AiAssistPanel";
import HireEmployeeModal from "./_components/HireEmployeeModal";
import BulkImportModal from "./_components/BulkImportModal";
import EmployeeDrawer from "./_components/EmployeeDrawer";
import AppraisalBanner from "./_components/AppraisalBanner";

const STATUS_FILTERS: { value: "all" | EmployeeStatusFilter; label: string }[] = [
  { value: "all",            label: "All Statuses"   },
  { value: "active",         label: "Active"         },
  { value: "onboarding",     label: "Onboarding"     },
  { value: "probation",      label: "Probation"      },
  { value: "notice_period",  label: "Notice Period"  },
  { value: "inactive",       label: "Exited"         },
];

// PreviewRoleProvider now wraps the whole dashboard (app/dashboard/layout.tsx)
// so the "Preview as" state set from the global nav switcher reaches this
// page's masking too — no local provider needed here anymore.
export default function EmployeesPage() {
  return <EmployeesPageInner />;
}

function EmployeesPageInner() {
  const router = useRouter();
  const canCreate = usePermission("employees.create");
  const canEdit = usePermission("employees.edit");
  const canEditOnboarding = usePermission("onboarding.edit");

  const emp = useEmployees();

  const [showModal, setShowModal] = useState(false);
  const [resumeDraftId, setResumeDraftId] = useState<string | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [showAiAssist, setShowAiAssist] = useState(false);
  const [drawerEmployee, setDrawerEmployee] = useState<Employee | null>(null);

  function open(id: string) {
    const found = emp.employees.find(e => e.id === id);
    if (found) { setDrawerEmployee(found); return; }
    router.push(`/dashboard/employees/${id}`);
  }

  return (
    <div>
      <EmployeeDirectoryHeader
        totalHeadcount={emp.total}
        canCreate={canCreate}
        exporting={emp.exporting}
        onResumeDraft={id => setResumeDraftId(id)}
        onOpenAiAssist={() => setShowAiAssist(true)}
        onExport={emp.handleExport}
        onHireEmployee={() => setShowModal(true)}
      />

      <EmployeeStatCards stats={emp.stats} />

      <AppraisalBanner />

      <EmployeeToolbar
        search={emp.search} onSearchChange={emp.setSearch}
        branch={emp.branch} branchOptions={emp.branchOptions} onBranchChange={emp.setBranch}
        isAdmin={emp.isAdmin} userBranch={emp.userBranch}
        dept={emp.dept} deptOptions={emp.deptOptions} onDeptChange={emp.setDept}
        status={emp.status} statusFilters={STATUS_FILTERS} onStatusChange={emp.setStatus}
        hasActiveFilters={!!(emp.search || emp.branch !== "all" || emp.dept !== "all" || emp.status !== "all")}
        onClearFilters={emp.clearFilters}
        canImport={canCreate} onBulkImport={() => setShowImport(true)}
      />

      <EmployeeTable
        employees={emp.employees}
        loading={emp.loading}
        fetchError={emp.fetchError}
        canEditOnboarding={canEditOnboarding}
        canEdit={canEdit}
        togglingId={emp.toggling}
        onOpen={open}
        onToggleStatus={emp.toggleStatus}
        onRetry={() => emp.fetchEmployees()}
        onActionApplied={() => emp.fetchEmployees()}
      />

      <Pagination
        page={emp.page} totalPages={emp.totalPages} totalCount={emp.totalCount}
        pageSize={20} itemLabel="employees" onPageChange={emp.handlePageChange}
      />

      {(showModal || resumeDraftId) && (
        <HireEmployeeModal
          initialHireActionId={resumeDraftId ?? undefined}
          onClose={() => { setShowModal(false); setResumeDraftId(null); }}
          onHired={() => emp.fetchEmployees(emp.search, 1)}
        />
      )}

      {showAiAssist && (
        <AiAssistPanel
          departments={emp.deptOptions}
          branches={emp.branchOptions}
          onClose={() => setShowAiAssist(false)}
          onApply={result => emp.applyFilters({ status: result.status, branch: result.branch, dept: result.department, search: result.search })}
        />
      )}

      {showImport && (
        <BulkImportModal onClose={() => setShowImport(false)} onSuccess={() => emp.fetchEmployees(emp.search, 1)} />
      )}

      {drawerEmployee && (
        <EmployeeDrawer employee={drawerEmployee} onClose={() => setDrawerEmployee(null)} />
      )}
    </div>
  );
}
