import { useCallback, useEffect, useState } from "react";
import { fetchEmployees, fetchEmployeeProfile } from "@/lib/api/employee";
import type { EmployeeProfile } from "@/lib/api/types";

const STORAGE_KEY = "hcs01.activeEmployee";

/**
 * Who is signed in, and everybody they can switch to.
 *
 * Nobody, until the directory has been read. It used to start as an invented persona and
 * keep it if the fetch failed, which meant a screen could not tell "we have not looked
 * yet" from "we looked and this is who it is" — and the invented people carried no
 * `employment_status`, so with the API down every new joiner read as a current employee.
 * `null` says the thing a placeholder person cannot.
 */
export function useActiveEmployee() {
  const [employees, setEmployees] = useState<EmployeeProfile[]>([]);
  const [employeeId, setEmployeeId] = useState<string>("");
  const [employee, setEmployee] = useState<EmployeeProfile | null>(null);
  /** The directory could not be read at all. */
  const [unreachable, setUnreachable] = useState(false);
  /**
   * Whether `employeeId` is the real answer yet.
   *
   * It starts empty and is filled once the directory has been fetched and the saved choice
   * read back. Anything keyed on the employee — the conversation store, most obviously —
   * is rebuilt when it changes, so work started before this is true can be thrown away
   * mid-flight. That is not a hypothetical: a question typed on the dashboard went into a
   * conversation that was discarded a moment later when the id settled to somebody else,
   * and it happened only when the saved persona differed from the default, which is why it
   * looked intermittent.
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
      // Nobody is signed in, and saying so is the whole point of removing the personas.
      if (!active) return;
      setUnreachable(true);
      setSettled(true);
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

    void fetchEmployeeProfile(id)
      .then((profile) => setEmployee(profile))
      .catch(() => {
        // Keep whoever the directory already gave us rather than blanking the header:
        // the list was read successfully a moment ago, so the person is real even if this
        // one request failed.
      });
  }, []);

  return { employee, employees, employeeId, selectEmployee, settled, unreachable };
}

