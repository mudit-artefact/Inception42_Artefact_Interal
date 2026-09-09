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
  /**
   * Whether `employeeId` is the real answer yet.
   *
   * It starts as a mock persona's id and is replaced once the directory has been fetched
   * and the saved choice read back. Anything keyed on the employee — the conversation
   * store, most obviously — is rebuilt when it changes, so work started before this is
   * true can be thrown away mid-flight. That is not a hypothetical: a question typed on
   * the dashboard went into a conversation that was discarded a moment later when the id
   * settled to somebody else, and it happened only when the saved persona differed from
   * the default, which is why it looked intermittent.
   */
  const [settled, setSettled] = useState(false);

  useEffect(() => {
    let active = true;

    void fetchEmployees().then((list) => {
      if (!active) return;
      if (!list.length) {
        setSettled(true);
        return;
      }
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
      setSettled(true);
    }).catch(() => {
      // The mock persona stands, and it is not going to change again.
      if (active) setSettled(true);
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

  return { employee, employees, employeeId, selectEmployee, settled };
}

