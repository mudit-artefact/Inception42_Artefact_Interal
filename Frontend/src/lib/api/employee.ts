import { apiRequest } from "./client";
import type { EmployeeProfile } from "./types";

/**
 * Everybody the directory holds.
 *
 * No mock fallback, and there used to be one — twelve invented personas substituted
 * whenever the API could not be reached. It was written before new joiners existed, so it
 * held twelve people where the directory holds eighteen, the six joiners were absent
 * altogether, and none of the twelve carried an `employment_status`.
 *
 * That last part is what made it worse than useless. Screens ask "is this a new joiner?"
 * by reading that field, and a field that is absent compares as **false rather than
 * unknown** — so with the API down, every joiner silently became a current employee and
 * was shown leave they cannot take instead of the visa documents they must send. A
 * fallback whose failure mode is confident wrongness is worse than no fallback.
 *
 * It throws now, like the leave functions below and for the same reason: a page that
 * cannot load says so.
 */
export async function fetchEmployees(): Promise<EmployeeProfile[]> {
  const data = await apiRequest<EmployeeProfile[]>("/api/omni/employees");
  if (!Array.isArray(data)) return [];
  return data.map((emp) => ({
    ...emp,
    id: emp.id || emp.user_id || "",
    jobTitle: emp.jobTitle || emp.role || "Employee",
    policyLinks: emp.policyLinks ?? [],
  }));
}

/** One person's profile. Throws if it cannot be read; see above. */
export async function fetchEmployeeProfile(employeeId: string): Promise<EmployeeProfile> {
  const data = await apiRequest<EmployeeProfile>(
    `/api/omni/employee/${encodeURIComponent(employeeId)}`,
  );
  return {
    ...data,
    id: data.id || data.user_id || employeeId,
    jobTitle: data.jobTitle || data.role || "Employee",
    policyLinks: data.policyLinks ?? [],
  };
}

/** One leave request as `My requests` lists it. */
export interface LeaveRequestRow {
  id: number;
  leave_type: string;
  start_date: string;
  end_date: string;
  days_requested: number;
  status: string;
  approver_name: string;
  notes: string;
  created_at: string;
}

/** One request waiting on this person's decision. */
export interface PendingApproval {
  request_id: number;
  employee_id: string;
  employee_name: string;
  employee_role: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  days_requested: number;
  notes: string;
  created_at: string;
  status: string;
}

/**
 * This employee's leave requests, newest first.
 *
 * No mock fallback, and now nothing above has one either — this function's argument
 * against inventing data was eventually taken by the whole file. It throws, and the page
 * says it could not load.
 */
export async function fetchLeaveRequests(employeeId: string): Promise<LeaveRequestRow[]> {
  return apiRequest<LeaveRequestRow[]>(
    `/api/omni/employee/${encodeURIComponent(employeeId)}/leave-requests`,
  );
}

/** Leave requests waiting on this person. Empty for anybody who manages nobody. */
export async function fetchPendingApprovals(employeeId: string): Promise<PendingApproval[]> {
  return apiRequest<PendingApproval[]>(
    `/api/omni/employee/${encodeURIComponent(employeeId)}/approvals`,
  );
}
