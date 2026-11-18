export interface AuditLogEntry {
  id:          number;
  actor_name:  string;
  actor_email: string | null;
  actor_role:  string | null;
  action:      string;
  description?: string;
  module:      string;
  object_id:   string;
  ip_address:  string | null;
  created_at:  string;
}

export interface AuditLogPage {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     AuditLogEntry[];
}
