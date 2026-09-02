import { useState } from "react";
import { Calendar as CalendarIcon, ChevronLeft, ChevronRight, Check, ArrowRight } from "lucide-react";
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

export function LeaveCalendarPicker({
  onSelectDates,
  leaveType = "Annual leave",
  minDate,
}: LeaveCalendarPickerProps) {
  const [selectedType, setSelectedType] = useState(leaveType);
  // Default to October 2026 for demonstration ease if not current year
  const initialDate = minDate ? new Date(minDate) : new Date(2026, 9, 1);
  const [currentYear, setCurrentYear] = useState(initialDate.getFullYear());
  const [currentMonth, setCurrentMonth] = useState(initialDate.getMonth()); // 0-indexed

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

  // Working days count (excluding Sat/Sun)
  const calculateDays = () => {
    if (!startDate) return 0;
    const end = endDate || startDate;
    let count = 0;
    const cur = new Date(startDate);
    const last = new Date(end);
    while (cur <= last) {
      const day = cur.getDay();
      if (day !== 0 && day !== 6) count++; // Not Sun (0) or Sat (6)
      cur.setDate(cur.getDate() + 1);
    }
    return count;
  };

  const workingDays = calculateDays();

  const isSelected = (dayStr: string) => {
    if (startDate === dayStr || endDate === dayStr) return true;
    if (startDate && endDate && dayStr > startDate && dayStr < endDate) return true;
    return false;
  };

  const isRangeEndpoint = (dayStr: string) => {
    return startDate === dayStr || endDate === dayStr;
  };

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-primary/20 bg-card/90 shadow-sm">
      <div className="flex items-center justify-between border-b border-border/60 bg-muted/30 px-3.5 py-2.5">
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
          className="rounded-md border border-border bg-background px-2 py-1 text-xs font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
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
              className="grid size-6 place-items-center rounded hover:bg-muted text-muted-foreground hover:text-foreground"
            >
              <ChevronLeft className="size-3.5" />
            </button>
            <button
              onClick={nextMonth}
              type="button"
              aria-label="Next month"
              className="grid size-6 place-items-center rounded hover:bg-muted text-muted-foreground hover:text-foreground"
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
            const isWeekend = new Date(currentYear, currentMonth, dayNum).getDay() % 6 === 0;

            return (
              <button
                key={dayStr}
                onClick={() => handleDateClick(dayStr)}
                type="button"
                className={`group relative flex h-7 items-center justify-center rounded-md font-medium transition-colors ${
                  endpoint
                    ? "bg-primary text-primary-foreground font-semibold"
                    : selected
                    ? "bg-primary/15 text-primary"
                    : isWeekend
                    ? "text-muted-foreground/50 hover:bg-muted/50"
                    : "text-foreground hover:bg-muted"
                }`}
              >
                {dayNum}
              </button>
            );
          })}
        </div>

        {/* Selection Summary Footer */}
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-2.5">
          <div className="text-[11px] text-muted-foreground">
            {startDate ? (
              <span className="flex items-center gap-1.5 font-medium text-foreground">
                <span className="rounded bg-muted px-1.5 py-0.5">{startDate}</span>
                <ArrowRight className="size-3 text-muted-foreground" />
                <span className="rounded bg-muted px-1.5 py-0.5">{endDate || startDate}</span>
                <span className="text-primary font-semibold">({workingDays} working days)</span>
              </span>
            ) : (
              <span>Click a start and end date</span>
            )}
          </div>

          <Button
            size="sm"
            disabled={!startDate}
            onClick={() => {
              if (startDate) {
                onSelectDates(selectedType, startDate, endDate || startDate);
              }
            }}
            className="h-7 gap-1.5 px-3 text-xs"
          >
            <Check className="size-3" />
            Apply for Dates
          </Button>
        </div>
      </div>
    </div>
  );
}
