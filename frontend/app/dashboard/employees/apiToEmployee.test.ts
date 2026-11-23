import { describe, expect, it } from "vitest";
import { apiToEmployee, type ApiEmployee } from "./_data";

// The directory list API returns `id` = the employee CODE (QA0001) and `uuid` = the database id. By-id endpoints (onboarding
// history, resend invite) need the uuid; mapping the code into `uuid` made them answer 404 for every row.
function row(fields: Partial<ApiEmployee>): ApiEmployee {
  // A test fixture fills only the fields this test is about; the rest of the large API shape is irrelevant here.
  return { id: "QA0001", employee_id: "QA0001", first_name: "Asha", last_name: "Rao", full_name: "Asha Rao", email: "a@example.com", phone: "",
    department: "", designation: "", branch: "", date_of_joining: "2025-01-01", is_active: true, status: "active", ...fields } as ApiEmployee;
}

describe("apiToEmployee", () => {
  it("keeps the real uuid from the API in `uuid`, and the employee code in `id` and `code`", () => {
    const mapped = apiToEmployee(row({ uuid: "b633abea-cb50-4c9d-a2ad-0bfffd8a665b" }));
    expect(mapped.uuid).toBe("b633abea-cb50-4c9d-a2ad-0bfffd8a665b");
    expect(mapped.id).toBe("QA0001");
    expect(mapped.code).toBe("QA0001");
  });

  it("falls back to the row id only when the API sent no uuid", () => {
    expect(apiToEmployee(row({})).uuid).toBe("QA0001");
  });
});
