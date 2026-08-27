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
}

const initialsOf = (name: string) =>
  (name || "Employee")
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("");

export function UserSwitcher({ employees, activeId, onSelect, className }: UserSwitcherProps) {
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
            <span className="block text-[11px] text-muted-foreground">{active.jobTitle || active.role}</span>
          </span>
          <ChevronsUpDown aria-hidden="true" className="size-3.5 shrink-0 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-[280px]">
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
          Simulate a different employee
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {employees.map((employee) => {
          const empId = employee.id || employee.user_id || "EMP001";
          const isActive = empId === activeId;
          return (
            <DropdownMenuItem
              key={empId}
              onSelect={() => onSelect(empId)}
              className="items-start gap-3 py-2"
            >
              <span
                aria-hidden="true"
                className={cn(
                  "grid size-8 shrink-0 place-items-center rounded-full bg-primary font-display text-[11px] font-semibold text-primary-foreground",
                  isActive && "ring-2 ring-pink ring-offset-1 ring-offset-popover",
                )}
              >
                {initialsOf(employee.name)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-xs font-semibold text-foreground">{employee.name}</span>
                <span className="block text-[11px] text-muted-foreground">{employee.jobTitle || employee.role}</span>
                <span className="block text-[11px] text-muted-foreground">
                  {employee.department} · {employee.grade}
                </span>
              </span>
              {isActive ? <Check aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-pink" /> : null}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

