import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
  Cell,
  TooltipProps,
} from "recharts";
import type { ChartData } from "@/lib/api/types";

// Clean, modern color palette
const COLORS = {
  primary: "#8b5cf6",    // violet
  secondary: "#ec4899",  // pink
  tertiary: "#06b6d4",   // cyan
  quaternary: "#10b981", // emerald
  accent: "#f59e0b",     // amber
};

const BAR_COLORS = [COLORS.primary, COLORS.secondary, COLORS.tertiary, COLORS.quaternary, COLORS.accent];

interface DataChartProps {
  chart: ChartData;
}

// Separate component for nested bar row with independent hover state
function NestedBarRow({
  item,
  index,
  barHeight,
  unit,
  series1Name,
  series2Name,
}: {
  item: { name: string; total: number; remaining: number };
  index: number;
  barHeight: number;
  unit: string;
  series1Name: string;
  series2Name: string;
}) {
  const [isHovered, setIsHovered] = useState(false);
  const percentage = item.total > 0 ? (item.remaining / item.total) * 100 : 0;

  return (
    <div className="relative">
      <div className="mb-1.5 text-xs font-medium text-foreground">{item.name}</div>
      {/* Bar container - full width */}
      <div
        className="relative w-full cursor-pointer rounded-lg bg-gray-200 dark:bg-gray-700"
        style={{ height: barHeight }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Foreground bar (Remaining) - width as percentage of total */}
        <div
          className="absolute left-0 top-0 rounded-lg transition-all duration-300"
          style={{
            width: `${percentage}%`,
            height: barHeight,
            backgroundColor: BAR_COLORS[index % BAR_COLORS.length],
          }}
        />
        {/* Tooltip - appears on hover */}
        {isHovered && (
          <div className="absolute -top-12 left-1/2 z-20 -translate-x-1/2 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center gap-2 whitespace-nowrap rounded-lg bg-gray-900 px-3 py-2 shadow-xl dark:bg-white">
              <span className="text-sm font-bold text-white dark:text-gray-900">
                {item.remaining}
              </span>
              <span className="text-xs text-gray-400 dark:text-gray-500">/</span>
              <span className="text-sm text-gray-300 dark:text-gray-600">
                {item.total}
              </span>
              <span className="text-xs text-gray-400 dark:text-gray-500">{unit}</span>
            </div>
            {/* Arrow */}
            <div className="absolute left-1/2 top-full -translate-x-1/2 border-[6px] border-transparent border-t-gray-900 dark:border-t-white" />
          </div>
        )}
      </div>
    </div>
  );
}

// Custom tooltip component for clean styling
function CustomTooltip({ active, payload, label, unit }: TooltipProps<number, string> & { unit?: string }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 shadow-lg">
      <p className="mb-1 text-xs font-medium text-foreground">{label}</p>
      {payload.map((entry, index) => (
        <p key={index} className="text-xs" style={{ color: entry.color }}>
          {entry.name}: <span className="font-semibold">{entry.value?.toLocaleString()}</span>
          {unit ? ` ${unit}` : ""}
        </p>
      ))}
    </div>
  );
}

export function DataChart({ chart }: DataChartProps) {
  const unit = chart.unit || "";

  // Nested Bar Chart (Total as background, Remaining/Actual as overlay)
  // Use for: balance questions, budget vs spent, quota vs used
  if (chart.chart_type === "nested_bar") {
    const series1Name = chart.series_names[0] || "Total";
    const series2Name = chart.series_names[1] || "Remaining";

    const data = chart.data.map((point) => ({
      name: point.label,
      total: point.value,
      remaining: point.value2 ?? 0,
    }));

    const barHeight = 28;

    return (
      <div className="mt-4 w-full rounded-xl border border-border/50 bg-card p-4">
        <h4 className="mb-3 text-sm font-semibold text-foreground">{chart.title}</h4>
        {/* Custom nested bars - all same width, inner shows percentage */}
        <div className="space-y-4">
          {data.map((item, index) => (
            <NestedBarRow
              key={index}
              item={item}
              index={index}
              barHeight={barHeight}
              unit={unit}
              series1Name={series1Name}
              series2Name={series2Name}
            />
          ))}
        </div>
        {/* Legend */}
        <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <div className="h-3 w-3 rounded bg-gray-200 dark:bg-gray-700" />
            <span>{series1Name}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-3 w-3 rounded" style={{ backgroundColor: COLORS.primary }} />
            <span>{series2Name}</span>
          </div>
        </div>
      </div>
    );
  }

  // Horizontal Bar Chart (single series comparison)
  if (chart.chart_type === "horizontal_bar") {
    const data = chart.data.map((point, index) => ({
      name: point.label,
      value: point.value,
      fill: BAR_COLORS[index % BAR_COLORS.length],
    }));

    const maxLabelLength = Math.max(...data.map(d => d.name.length));
    const yAxisWidth = Math.min(Math.max(maxLabelLength * 7, 80), 140);

    return (
      <div className="mt-4 w-full rounded-xl border border-border/50 bg-card p-4">
        <h4 className="mb-3 text-sm font-semibold text-foreground">{chart.title}</h4>
        <div style={{ height: Math.max(data.length * 50, 120) }} className="w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 5, bottom: 5 }}
              barCategoryGap="20%"
            >
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: "#6b7280" }}
                axisLine={{ stroke: "#e5e7eb" }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fontSize: 11, fill: "#374151" }}
                axisLine={false}
                tickLine={false}
                width={yAxisWidth}
              />
              <Tooltip content={<CustomTooltip unit={unit} />} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={24}>
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  // Grouped Bar Chart (side-by-side comparison)
  if (chart.chart_type === "grouped_bar") {
    const series1Name = chart.series_names[0] || "Series 1";
    const series2Name = chart.series_names[1] || "Series 2";

    const data = chart.data.map((point) => ({
      name: point.label,
      [series1Name]: point.value,
      [series2Name]: point.value2 ?? 0,
    }));

    return (
      <div className="mt-4 w-full rounded-xl border border-border/50 bg-card p-4">
        <h4 className="mb-3 text-sm font-semibold text-foreground">{chart.title}</h4>
        <div className="h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              margin={{ top: 10, right: 20, left: 0, bottom: 5 }}
              barCategoryGap="25%"
              barGap={3}
            >
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11, fill: "#374151" }}
                axisLine={{ stroke: "#e5e7eb" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#6b7280" }}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip content={<CustomTooltip unit={unit} />} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
              <Legend
                verticalAlign="top"
                height={30}
                iconType="circle"
                iconSize={8}
                formatter={(value) => <span className="text-xs text-muted-foreground">{value}</span>}
              />
              <Bar
                dataKey={series1Name}
                fill={COLORS.primary}
                radius={[4, 4, 0, 0]}
                barSize={32}
              />
              <Bar
                dataKey={series2Name}
                fill={COLORS.secondary}
                radius={[4, 4, 0, 0]}
                barSize={32}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  // Stacked Bar Chart (parts of whole)
  if (chart.chart_type === "stacked_bar") {
    const series1Name = chart.series_names[0] || "Series 1";
    const series2Name = chart.series_names[1] || "Series 2";

    const data = chart.data.map((point) => ({
      name: point.label,
      [series1Name]: point.value,
      [series2Name]: point.value2 ?? 0,
    }));

    const maxLabelLength = Math.max(...data.map(d => d.name.length));
    const yAxisWidth = Math.min(Math.max(maxLabelLength * 7, 80), 140);

    return (
      <div className="mt-4 w-full rounded-xl border border-border/50 bg-card p-4">
        <h4 className="mb-3 text-sm font-semibold text-foreground">{chart.title}</h4>
        <div style={{ height: Math.max(data.length * 50, 100) }} className="w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 5, right: 30, left: 5, bottom: 5 }}
              barCategoryGap="25%"
            >
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: "#6b7280" }}
                axisLine={{ stroke: "#e5e7eb" }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fontSize: 11, fill: "#374151" }}
                axisLine={false}
                tickLine={false}
                width={yAxisWidth}
              />
              <Tooltip content={<CustomTooltip unit={unit} />} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
              <Legend
                verticalAlign="top"
                height={30}
                iconType="circle"
                iconSize={8}
                formatter={(value) => <span className="text-xs text-muted-foreground">{value}</span>}
              />
              <Bar
                dataKey={series1Name}
                stackId="stack"
                fill={COLORS.primary}
                barSize={28}
              />
              <Bar
                dataKey={series2Name}
                stackId="stack"
                fill={COLORS.secondary}
                radius={[0, 4, 4, 0]}
                barSize={28}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  // Progress Bar (single value against max)
  if (chart.chart_type === "progress") {
    const current = chart.data[0]?.value || 0;
    const max = chart.max_value || 100;
    const percentage = Math.min(Math.round((current / max) * 100), 100);
    const remaining = max - current;
    const label = chart.data[0]?.label || "Used";

    return (
      <div className="mt-4 w-full rounded-xl border border-border/50 bg-card p-4">
        <h4 className="mb-3 text-sm font-semibold text-foreground">{chart.title}</h4>
        <div className="space-y-3">
          <div className="flex items-baseline justify-between">
            <div>
              <span className="text-2xl font-bold text-foreground">{current}</span>
              <span className="ml-1 text-sm text-muted-foreground">/ {max} {unit}</span>
            </div>
            <span className="text-lg font-semibold text-primary">{percentage}%</span>
          </div>
          <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-pink-500 transition-all duration-500"
              style={{ width: `${percentage}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>{label}: {current} {unit}</span>
            <span>Remaining: {remaining} {unit}</span>
          </div>
        </div>
      </div>
    );
  }

  // Line Chart (trends over time)
  if (chart.chart_type === "line") {
    const data = chart.data.map((point) => ({
      name: point.label,
      value: point.value,
    }));

    return (
      <div className="mt-4 w-full rounded-xl border border-border/50 bg-card p-4">
        <h4 className="mb-3 text-sm font-semibold text-foreground">{chart.title}</h4>
        <div className="h-[180px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11, fill: "#6b7280" }}
                axisLine={{ stroke: "#e5e7eb" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#6b7280" }}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip content={<CustomTooltip unit={unit} />} cursor={{ stroke: "#e5e7eb" }} />
              <Line
                type="monotone"
                dataKey="value"
                name="Value"
                stroke={COLORS.primary}
                strokeWidth={2.5}
                dot={{ fill: COLORS.primary, strokeWidth: 0, r: 4 }}
                activeDot={{ r: 6, fill: COLORS.secondary }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  return null;
}
