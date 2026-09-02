import { useState } from "react";
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, Check, ArrowRight, Sparkles, Info } from "lucide-react";
import { Button } from "@/components/ui/button";

interface LeaveCalendarPickerProps {
  onSelectDates: (leaveType: string, startDate: string, endDate: string) => void;
  leaveType?: string;
  minDate?: string;
}

const LEAVE_TYPES = [
  "Annual leave",
  "Sick leave",
  "Emergency leave",
];

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

const DAYS_OF_WEEK = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

// Official UAE Public Holidays for 2026
const UAE_PUBLIC_HOLIDAYS_2026: Record<string, string> = {
  "2026-01-01": "New Year's Day",
  "2026-03-20": "Eid Al Fitr",
  "2026-03-21": "Eid Al Fitr",
  "2026-03-22": "Eid Al Fitr",
  "2026-05-27": "Arafat Day",
  "2026-05-28": "Eid Al Adha",
  "2026-05-29": "Eid Al Adha",
  "2026-06-17": "Islamic New Year",
  "2026-12-01": "Commemoration Day",
  "2026-12-02": "UAE National Day",
  "2026-12-03": "National Day Holiday",
};

export function LeaveCalendarPicker({
  onSelectDates,
  leaveType = "Annual leave",
  minDate,
}: LeaveCalendarPickerProps) {
  const [selectedType, setSelectedType] = useState(leaveType);

  // Parse initial year/month safely without UTC timezone shift
  let initialYear = 2026;
  let initialMonth = 9; // October (0-indexed 9)
  if (minDate) {
    const parts = minDate.split("-");
    if (parts.length === 3) {
      initialYear = parseInt(parts[0], 10);
      initialMonth = parseInt(parts[1], 10) - 1;
    }
  }

  const [currentYear, setCurrentYear] = useState(initialYear);
  const [currentMonth, setCurrentMonth] = useState(initialMonth);

  const [startDate, setStartDate] = useState<string | null>(null);
  const [endDate, setEndDate] = useState<string | null>(null);

  // Month navigation
  const prevMonth = () => {
    if (currentMonth === 0) {
      setCurrentMonth(11);
      setCurrentYear(currentYear - 1);
    } else {
      setCurrentMonth(currentMonth - 1);
    }
  };

  const nextMonth = () => {
    if (currentMonth === 11) {
      setCurrentMonth(0);
      setCurrentYear(currentYear + 1);
    } else {
      setCurrentMonth(currentMonth + 1);
    }
  };

  // Days in month
  const firstDayOfWeek = (new Date(currentYear, currentMonth, 1).getDay() + 6) % 7; // Monday = 0
  const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();

  const formatDateStr = (year: number, month: number, day: number) => {
    const m = String(month + 1).padStart(2, "0");
    const d = String(day).padStart(2, "0");
    return `${year}-${m}-${d}`;
  };

  const handleDateClick = (dayStr: string) => {
    if (!startDate || (startDate && endDate)) {
      setStartDate(dayStr);
      setEndDate(null);
    } else {
      // If clicked date is before start date, swap
      if (dayStr < startDate) {
        setEndDate(startDate);
        setStartDate(dayStr);
      } else {
        setEndDate(dayStr);
      }
    }
  };

  // Working days count (excluding Sat/Sun and UAE Public Holidays)
  const calculateDays = () => {
    if (!startDate) return { workingDays: 0, holidayCount: 0, holidaysInRange: [] as string[] };
    const end = endDate || startDate;
    let workingDays = 0;
    let holidayCount = 0;
    const holidaysInRange: string[] = [];

    const cur = new Date(`${startDate}T00:00:00`);
    const last = new Date(`${end}T00:00:00`);

    while (cur <= last) {
      const dayOfWeek = cur.getDay();
      const y = cur.getFullYear();
      const m = String(cur.getMonth() + 1).padStart(2, "0");
      const d = String(cur.getDate()).padStart(2, "0");
      const iso = `${y}-${m}-${d}`;

      const isWeekend = dayOfWeek === 0 || dayOfWeek === 6; // Sunday or Saturday
      const holidayName = UAE_PUBLIC_HOLIDAYS_2026[iso];

      if (holidayName) {
        holidayCount++;
        holidaysInRange.push(`${iso} (${holidayName})`);
      } else if (!isWeekend) {
        workingDays++;
      }

      cur.setDate(cur.getDate() + 1);
    }

    return { workingDays, holidayCount, holidaysInRange };
  };

  const { workingDays, holidayCount, holidaysInRange } = calculateDays();

  const isSelected = (dayStr: string) => {
    if (startDate === dayStr || endDate === dayStr) return true;
    if (startDate && endDate && dayStr > startDate && dayStr < endDate) return true;
    return false;
  };

  const isRangeEndpoint = (dayStr: string) => {
    return startDate === dayStr || endDate === dayStr;
  };

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-primary/25 bg-card/95 shadow-sm">
      <div className="flex items-center justify-between border-b border-border/60 bg-muted/40 px-3.5 py-2.5">
        <div className="flex items-center gap-2">
          <span className="grid size-6 place-items-center rounded-md bg-primary/10 text-primary">
            <CalendarIcon className="size-3.5" />
          </span>
          <span className="font-display text-xs font-semibold text-foreground">
            Select Leave Dates
          </span>
        </div>

        {/* Leave Type Selector */}
        <select
          value={selectedType}
          onChange={(e) => setSelectedType(e.target.value)}
          aria-label="Select leave type"
          className="rounded-md border border-border bg-background px-2.5 py-1 text-xs font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        >
          {LEAVE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <div className="p-3">
        {/* Month Navigation */}
        <div className="mb-2 flex items-center justify-between">
          <span className="font-display text-xs font-semibold text-foreground">
            {MONTH_NAMES[currentMonth]} {currentYear}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={prevMonth}
              type="button"
              aria-label="Previous month"
              className="grid size-6 place-items-center rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            >
              <ChevronLeft className="size-3.5" />
            </button>
            <button
              onClick={nextMonth}
              type="button"
              aria-label="Next month"
              className="grid size-6 place-items-center rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            >
              <ChevronRight className="size-3.5" />
            </button>
          </div>
        </div>

        {/* Calendar Grid */}
        <div className="grid grid-cols-7 gap-1 text-center text-[11px]">
          {DAYS_OF_WEEK.map((d) => (
            <div key={d} className="py-1 font-semibold text-muted-foreground">
              {d}
            </div>
          ))}

          {/* Empty padding days */}
          {Array.from({ length: firstDayOfWeek }).map((_, i) => (
            <div key={`empty-${i}`} className="py-1" />
          ))}

          {/* Month Days */}
          {Array.from({ length: daysInMonth }).map((_, i) => {
            const dayNum = i + 1;
            const dayStr = formatDateStr(currentYear, currentMonth, dayNum);
            const selected = isSelected(dayStr);
            const endpoint = isRangeEndpoint(dayStr);
            const isWeekend = new Date(`${dayStr}T00:00:00`).getDay() % 6 === 0;
            const holidayName = UAE_PUBLIC_HOLIDAYS_2026[dayStr];

            return (
              <button
                key={dayStr}
                onClick={() => handleDateClick(dayStr)}
                type="button"
                title={holidayName ? `UAE Public Holiday: ${holidayName}` : dayStr}
                className={`group relative flex h-7 items-center justify-center rounded-md font-medium transition-colors ${
                  endpoint
                    ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                    : selected
                    ? "bg-primary/15 text-primary"
                    : holidayName
                    ? "bg-amber-500/10 text-amber-700 dark:text-amber-400 font-semibold border border-amber-500/30"
                    : isWeekend
                    ? "text-muted-foreground/45 hover:bg-muted/40"
                    : "text-foreground hover:bg-muted"
                }`}
              >
                <span>{dayNum}</span>
                {holidayName && !endpoint && (
                  <span className="absolute -top-0.5 -right-0.5 size-1.5 rounded-full bg-amber-500" />
                )}
              </button>
            );
          })}
        </div>

        {/* Legend */}
        <div className="mt-2.5 flex items-center justify-end gap-3 text-[10px] text-muted-foreground border-t border-border/40 pt-2">
          <span className="flex items-center gap-1">
            <span className="size-2 rounded-full bg-amber-500 inline-block" />
            <span>UAE Public Holiday</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="size-2 rounded-full bg-primary inline-block" />
            <span>Selected</span>
          </span>
        </div>

        {/* Selection Summary Footer */}
        <div className="mt-2.5 flex flex-col gap-2 border-t border-border/60 pt-2.5">
          <div className="text-[11px] text-muted-foreground">
            {startDate ? (
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-1.5 font-medium text-foreground">
                  <span className="rounded bg-muted px-1.5 py-0.5">{startDate}</span>
                  <ArrowRight className="size-3 text-muted-foreground" />
                  <span className="rounded bg-muted px-1.5 py-0.5">{endDate || startDate}</span>
                  {workingDays > 0 ? (
                    <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                      ({workingDays} working {workingDays === 1 ? "day" : "days"})
                    </span>
                  ) : (
                    <span className="text-amber-600 dark:text-amber-400 font-semibold">
                      (0 working days)
                    </span>
                  )}
                </div>

                {holidayCount > 0 && (
                  <p className="text-[10px] text-amber-600 dark:text-amber-400 flex items-center gap-1">
                    <Info className="size-3 shrink-0" />
                    <span>
                      Includes {holidayCount} official UAE public {holidayCount === 1 ? "holiday" : "holidays"} (no leave balance deducted).
                    </span>
                  </p>
                )}

                {workingDays === 0 && (
                  <p className="text-[10px] text-rose-600 dark:text-rose-400 font-medium">
                    ⚠️ Selected dates fall entirely on non-working days or official holidays. Please select dates with regular working days.
                  </p>
                )}
              </div>
            ) : (
              <span>Click start and end dates on the calendar</span>
            )}
          </div>

          <div className="flex justify-end">
            <Button
              size="sm"
              disabled={!startDate || workingDays === 0}
              onClick={() => {
                if (startDate && workingDays > 0) {
                  onSelectDates(selectedType, startDate, endDate || startDate);
                }
              }}
              className="h-7 gap-1.5 px-3.5 text-xs bg-pink hover:bg-pink/90 text-white disabled:opacity-50"
            >
              <Check className="size-3" />
              Apply for Dates
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
