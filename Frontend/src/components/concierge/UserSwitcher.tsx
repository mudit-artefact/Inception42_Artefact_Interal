import { Check, ChevronsUpDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { EmployeeProfile } from "@/lib/api/types";
import { cn } from "@/lib/utils";


interface UserSwitcherProps {
  employees: EmployeeProfile[];
  activeId: string;
  onSelect: (id: string) => void;
  className?: string;
  /**
   * What to call the signed-in person's job, when something knows better than the record.
   *
   * A new joiner's employment contract states their job title, and for all six of them it
   * differs from the title seeded in our own database — Fatima is a Director here and a
   * Finance Manager on the contract she is being asked to sign. Showing our version in the
   * header above a panel showing hers is the contradiction, and the contract is the
   * document she signs, so the contract wins.
   *
   * Only the trigger, never the list below it: the list is a switcher over everybody, and
   * it has no contract for anyone but the person currently signed in.
   */
  activeJobTitle?: string | null | undefined;
}

const initialsOf = (name: string) =>
  (name || "Employee")
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("");

/**
 * Two kinds of person, in the order somebody demonstrating this would want them.
 *
 * A new joiner has not started, so almost everything about them differs — no leave
 * balance, a visa application instead of a schooling claim, and every leave rule turning
 * them away. Finding one should not mean scrolling past twelve people who behave the
 * other way.
 */
const GROUPS = [
  {
    heading: "Employees",
    matches: (e: EmployeeProfile) => e.employment_status !== "Onboarding",
  },
  {
    heading: "New joiners",
    matches: (e: EmployeeProfile) => e.employment_status === "Onboarding",
  },
];

export function UserSwitcher({
  employees,
  activeId,
  onSelect,
  className,
  activeJobTitle,
}: UserSwitcherProps) {
  const active = employees.find((e) => e.id === activeId || e.user_id === activeId) ?? employees[0]!;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          className={cn("h-auto gap-2 px-2 py-1.5 text-left", className)}
          aria-label={`Signed in as ${active.name}. Switch user`}
        >
          <span
            aria-hidden="true"
            className="grid size-8 shrink-0 place-items-center rounded-full bg-primary font-display text-[11px] font-semibold tracking-wide text-primary-foreground"
          >
            {initialsOf(active.name)}
          </span>
          <span className="hidden min-w-0 sm:block">
            <span className="block text-xs font-semibold text-foreground">{active.name}</span>
            <span className="block text-[11px] text-muted-foreground">
              {activeJobTitle || active.jobTitle || active.role}
            </span>
          </span>
          <ChevronsUpDown aria-hidden="true" className="size-3.5 shrink-0 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-[280px]">
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
          Simulate a different employee
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {/*
          Split, and each row two lines rather than three.

          The list has grown from twelve people to eighteen, and at three lines each the
          menu needed 1202px. It scrolls, but nothing on it says so — so the six new
          joiners, who happen to sit last, simply looked as though they had been deleted.
          Shorter rows fit them on an ordinary screen, and the heading says they are there
          even when they have to be scrolled to.
        */}
        {GROUPS.map(({ heading, matches }) => {
          const people = employees.filter(matches);
          if (people.length === 0) return null;
          return (
            <div key={heading}>
              <DropdownMenuLabel className="px-2 pt-2 pb-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                {heading} ({people.length})
              </DropdownMenuLabel>
              {people.map((employee) => {
                const empId = employee.id || employee.user_id || "EMP001";
                const isActive = empId === activeId;
                return (
                  <DropdownMenuItem
                    key={empId}
                    onSelect={() => onSelect(empId)}
                    className="items-center gap-2.5 py-1.5"
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        "grid size-7 shrink-0 place-items-center rounded-full bg-primary font-display text-[10px] font-semibold text-primary-foreground",
                        isActive && "ring-2 ring-primary ring-offset-1 ring-offset-popover",
                      )}
                    >
                      {initialsOf(employee.name)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-semibold text-foreground">
                        {employee.name}
                      </span>
                      <span className="block truncate text-[11px] text-muted-foreground">
                        {employee.jobTitle || employee.role}
                      </span>
                    </span>
                    {isActive ? (
                      <Check aria-hidden="true" className="size-4 shrink-0 text-primary" />
                    ) : null}
                  </DropdownMenuItem>
                );
              })}
            </div>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

