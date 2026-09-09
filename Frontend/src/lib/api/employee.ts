import { apiRequest } from "./client";
import { isApiConfigured } from "./config";
import { MOCK_EMPLOYEES, getMockEmployee, type MockPersona } from "./mock";
import type { EmployeeProfile } from "./types";

/**
 * Fetch list of all employees from Mock Omni API.
 * Falls back to mock personas if API is not configured or fails.
 */
export async function fetchEmployees(): Promise<EmployeeProfile[]> {
  if (!isApiConfigured()) {
    return MOCK_EMPLOYEES;
  }

  try {
    const data = await apiRequest<EmployeeProfile[]>("/api/omni/employees");
    if (Array.isArray(data) && data.length > 0) {
      return data.map((emp) => ({
        ...emp,
        id: emp.id || emp.user_id || "EMP001",
        jobTitle: emp.jobTitle || emp.role || "Employee",
        policyLinks: emp.policyLinks ?? [],
      }));
    }
    return MOCK_EMPLOYEES;
  } catch (err) {
    console.warn("Failed to fetch employees from API, falling back to mock data:", err);
    return MOCK_EMPLOYEES;
  }
}

/**
 * Fetch a single employee profile by ID.
 * Falls back to mock persona if API is not configured or fails.
 */
export async function fetchEmployeeProfile(employeeId: string): Promise<EmployeeProfile> {
  if (!isApiConfigured()) {
    return getMockEmployee(employeeId);
  }

  try {
    const data = await apiRequest<EmployeeProfile>(`/api/omni/employee/${encodeURIComponent(employeeId)}`);
    return {
      ...data,
      id: data.id || data.user_id || employeeId,
      jobTitle: data.jobTitle || data.role || "Employee",
      policyLinks: data.policyLinks ?? [],
    };
  } catch (err) {
    console.warn(`Failed to fetch employee ${employeeId} from API, falling back to mock:`, err);
    return getMockEmployee(employeeId);
  }
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
 * No mock fallback, deliberately. The two functions above quietly substitute five invented
 * personas when the API is down, which is cosmetic on a chat and dishonest on a page headed
 * "My requests" — it would show somebody leave they never asked for. This throws, and the
 * page says it could not load.
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
