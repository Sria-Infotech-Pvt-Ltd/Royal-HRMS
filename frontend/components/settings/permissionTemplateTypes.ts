export interface PermissionTemplate {
  id:                   string;
  name:                 string;
  description:          string;
  can_manage_team:      boolean;
  can_manage_branch:    boolean;
  permission_codenames: string[];
  position_count:       number;
  created_at:           string;
  updated_at:           string;
}
