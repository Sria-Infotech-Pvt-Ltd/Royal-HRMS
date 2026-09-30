export type AssetStatus =
  | "available" | "assigned" | "under_repair" | "lost" | "damaged" | "retired" | "disposed";

export type AssetCondition = "new" | "good" | "fair" | "damaged";

export const ASSET_STATUS_OPTIONS: { value: AssetStatus; label: string }[] = [
  { value: "available",    label: "Available" },
  { value: "assigned",     label: "Assigned" },
  { value: "under_repair", label: "Under Repair" },
  { value: "lost",         label: "Lost" },
  { value: "damaged",      label: "Damaged" },
  { value: "retired",      label: "Retired" },
  { value: "disposed",     label: "Disposed" },
];

export const ASSET_CONDITION_OPTIONS: { value: AssetCondition; label: string }[] = [
  { value: "new",     label: "New" },
  { value: "good",    label: "Good" },
  { value: "fair",    label: "Fair" },
  { value: "damaged", label: "Damaged" },
];

export interface Asset {
  id: string;
  asset_tag: string;
  asset_name: string;
  category: string;
  asset_type: string;
  brand: string;
  model: string;
  serial_number: string | null;
  purchase_date: string | null;
  purchase_price: string | null;
  vendor: string;
  warranty_start_date: string | null;
  warranty_end_date: string | null;
  branch: number | string;
  branch_name: string;
  status: AssetStatus;
  status_display: string;
  condition: AssetCondition;
  condition_display: string;
  description: string;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface AssetAssignment {
  id: string;
  asset: string;
  asset_tag: string;
  asset_name: string;
  asset_type: string;
  serial_number: string | null;
  employee: string;
  employee_name: string;
  status: "assigned" | "returned";
  status_display: string;
  assigned_date: string;
  condition_at_assignment: AssetCondition;
  expected_return_date: string | null;
  assign_remarks: string;
  assigned_by: string | null;
  assigned_by_name: string | null;
  return_date: string | null;
  return_condition: AssetCondition | "";
  return_reason: string;
  return_remarks: string;
  returned_by: string | null;
  returned_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmployeeAssetsResponse {
  current: AssetAssignment[];
  history: AssetAssignment[];
}
