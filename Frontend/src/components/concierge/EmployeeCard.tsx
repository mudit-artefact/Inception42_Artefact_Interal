import { ExternalLink, FileText } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import type { EmployeeProfile, PolicySource } from "@/lib/api/types";

interface EmployeeCardProps {
  employee: EmployeeProfile;
  policyLinks?: PolicySource[];
}

export function EmployeeCard({ employee, policyLinks = [] }: EmployeeCardProps) {
  const initials = (employee.name || "Employee")
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("");

  const balances = employee.balances ?? [];
  const links = policyLinks?.length ? policyLinks : employee.policyLinks ?? [];

  return (
    <section aria-labelledby="employee-card-heading" className="rounded-xl border bg-card shadow-soft">
      <div className="flex items-center gap-3 border-b p-4">
        <span
          aria-hidden="true"
          className="grid size-11 shrink-0 place-items-center rounded-lg bg-primary font-display text-sm font-semibold tracking-wide text-primary-foreground"
        >
          {initials}
        </span>
        <div className="min-w-0">
          <h2 id="employee-card-heading" className="font-display text-sm font-semibold text-foreground">
            {employee.name}
          </h2>
          <p className="text-xs text-muted-foreground">
            {employee.jobTitle || employee.role} · {employee.grade}
          </p>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-3 border-b p-4 text-xs">
        <div className="min-w-0">
          <dt className="text-muted-foreground">Employee ID</dt>
          <dd className="font-medium text-foreground">{employee.id || employee.user_id}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-muted-foreground">Line manager</dt>
          <dd className="font-medium text-foreground">{employee.manager}</dd>
        </div>
      </dl>

      <div className="space-y-4 border-b p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Leave balance
        </h3>
        {balances.length === 0 ? (
          <p className="text-xs text-muted-foreground">No balance data available.</p>
        ) : (
          balances.map((b) => {
            // Sent by the API, never derived here. entitled - used ignores carried-over
            // days, so this panel used to show 12 where the assistant correctly said 15
            // — a contradiction between two halves of the same screen.
            const available = b.entitled + b.carry_over;
            const pct = available > 0 ? Math.min(100, (b.remaining / available) * 100) : 0;
            return (
              <div key={`${b.type}-${b.year}`}>
                <div className="flex items-baseline justify-between gap-2 text-xs">
                  <span className="font-medium text-foreground">{b.type}</span>
                  <span className="tabular-nums text-muted-foreground">
                    <span className="font-display text-sm font-semibold text-foreground">{b.remaining}</span> /{" "}
                    {available} {b.unit} left
                  </span>
                </div>
                <Progress
                  value={pct}
                  aria-label={`${b.type}: ${b.remaining} of ${available} ${b.unit} remaining`}
                  className="mt-2 h-1.5"
                />
                {b.carry_over > 0 ? (
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Includes {b.carry_over} {b.unit} carried over
                  </p>
                ) : null}
              </div>
            );
          })
        )}
      </div>

      <div className="p-4">
        <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Relevant policies
        </h3>
        <ul className="space-y-1">
          {links.map((link) => (
            <li key={link.id ?? link.title}>
              <a
                href={link.url ?? "#"}
                className="group flex items-start gap-2 rounded-md px-2 py-2 text-xs transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <FileText aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-pink" />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium text-foreground">{link.title}</span>
                  {link.section ? (
                    <Badge variant="secondary" className="mt-1 font-normal">
                      {link.section.replace(/§\s*/g, "Section ").replace(/§/g, "Section ")}
                    </Badge>
                  ) : null}
                </span>
                <ExternalLink
                  aria-hidden="true"
                  className="mt-0.5 size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                />
              </a>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

