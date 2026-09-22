export interface EmployeeBulkImportCreatedRow {
  row:         number;
  identifier:  string;
  employee_id: string;
  email_sent:  boolean;
}

export interface EmployeeBulkImportSkippedRow {
  row:        number;
  identifier: string;
  reason:     string;
}

export interface EmployeeBulkImportError {
  row:        number;
  field:      string;
  identifier: string;
  message:    string;
}

export interface EmployeeBulkImportResult {
  total_rows:           number;
  created:              number;
  skipped:              number;
  failed:               number;
  created_employee_ids: string[];
  created_rows:         EmployeeBulkImportCreatedRow[];
  skipped_rows:         EmployeeBulkImportSkippedRow[];
  errors:               EmployeeBulkImportError[];
}
