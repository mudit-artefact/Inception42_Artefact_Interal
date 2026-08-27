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
