import { useCallback, useEffect, useState } from "react";
import { fetchEmployees, fetchEmployeeProfile } from "@/lib/api/employee";
import { MOCK_EMPLOYEE, MOCK_EMPLOYEES, getMockEmployee } from "@/lib/api/mock";
import type { EmployeeProfile } from "@/lib/api/types";

const STORAGE_KEY = "hcs01.activeEmployee";

/**
 * Persona switcher that connects to Mock Omni backend while falling back
 * gracefully to local mock personas.
 */
export function useActiveEmployee() {
  const [employees, setEmployees] = useState<EmployeeProfile[]>(MOCK_EMPLOYEES);
  const [employeeId, setEmployeeId] = useState<string>(MOCK_EMPLOYEE.id);
  const [employee, setEmployee] = useState<EmployeeProfile>(MOCK_EMPLOYEE);

  useEffect(() => {
    let active = true;

    void fetchEmployees().then((list) => {
      if (!active || !list.length) return;
      setEmployees(list);

      let initialId = list[0]!.id;
      try {
        const stored = window.localStorage.getItem(STORAGE_KEY);
        if (stored && list.some((e) => e.id === stored || e.user_id === stored)) {
          initialId = stored;
        }
      } catch {
        /* storage disabled */
      }

      setEmployeeId(initialId);
      const found = list.find((e) => e.id === initialId || e.user_id === initialId) ?? list[0]!;
      setEmployee(found);
    });

    return () => {
      active = false;
    };
  }, []);

  const selectEmployee = useCallback((id: string) => {
    setEmployeeId(id);
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* ignore */
    }

    void fetchEmployeeProfile(id).then((profile) => {
      setEmployee(profile);
    });
  }, []);

  return { employee, employees, employeeId, selectEmployee };
}

