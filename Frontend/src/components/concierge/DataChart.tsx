import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
} from "recharts";
import { BarChart3, PieChart as PieIcon, TrendingUp } from "lucide-react";

import type { ChartPayload, ChartDataPoint } from "@/lib/api/types";
export type { ChartPayload, ChartDataPoint };

interface DataChartProps {
  chart?: ChartPayload | null | undefined;
}

const COLORS = [
  "#E6007E", // Inception pink
  "#8B5CF6", // Purple
  "#3B82F6", // Blue
  "#10B981", // Emerald
  "#F59E0B", // Amber
  "#6366F1", // Indigo
];

export function DataChart({ chart }: DataChartProps) {
  if (!chart || !chart.data || !Array.isArray(chart.data) || chart.data.length === 0) {
    return null;
  }

  const chartType = chart.type || "bar";
  const dataKey = chart.dataKey || "value";
  const xAxisKey = chart.xAxisKey || "name";

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-border/60 bg-muted/30 p-4 shadow-sm">
      {chart.title ? (
        <div className="mb-3 flex items-center gap-2">
          {chartType === "pie" ? (
            <PieIcon className="size-4 text-pink" />
          ) : chartType === "line" ? (
            <TrendingUp className="size-4 text-pink" />
          ) : (
            <BarChart3 className="size-4 text-pink" />
          )}
          <h4 className="font-display text-xs font-semibold text-foreground">
            {chart.title}
          </h4>
        </div>
      ) : null}

      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {chartType === "pie" ? (
            <PieChart>
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const item = payload[0];
                    return (
                      <div className="rounded-lg border border-border bg-popover px-3 py-1.5 text-xs shadow-md">
                        <p className="font-medium text-popover-foreground">{item?.name}</p>
                        <p className="text-muted-foreground">
                          {item?.value} {chart.unit ?? ""}
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Pie
                data={chart.data}
                cx="50%"
                cy="50%"
                innerRadius={38}
                outerRadius={65}
                paddingAngle={4}
                dataKey={dataKey}
                nameKey={xAxisKey}
              >
                {chart.data.map((_entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Pie>
            </PieChart>
          ) : chartType === "line" ? (
            <LineChart data={chart.data} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border/40" />
              <XAxis
                dataKey={xAxisKey}
                tick={{ fontSize: 11 }}
                className="text-muted-foreground"
              />
              <YAxis
                tick={{ fontSize: 11 }}
                className="text-muted-foreground"
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    return (
                      <div className="rounded-lg border border-border bg-popover px-3 py-1.5 text-xs shadow-md">
                        <p className="font-medium text-popover-foreground">{label}</p>
                        <p className="text-pink font-semibold">
                          {payload[0]?.value} {chart.unit ?? ""}
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Line
                type="monotone"
                dataKey={dataKey}
                stroke="#E6007E"
                strokeWidth={2.5}
                dot={{ fill: "#E6007E", r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          ) : (
            <BarChart data={chart.data} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border/40" />
              <XAxis
                dataKey={xAxisKey}
                tick={{ fontSize: 11 }}
                className="text-muted-foreground"
              />
              <YAxis
                tick={{ fontSize: 11 }}
                className="text-muted-foreground"
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (active && payload && payload.length) {
                    return (
                      <div className="rounded-lg border border-border bg-popover px-3 py-1.5 text-xs shadow-md">
                        <p className="font-medium text-popover-foreground">{label}</p>
                        <p className="text-pink font-semibold">
                          {payload[0]?.value} {chart.unit ?? ""}
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Bar dataKey={dataKey} fill="#E6007E" radius={[6, 6, 0, 0]}>
                {chart.data.map((_entry, index) => (
                  <Cell
                    key={`bar-cell-${index}`}
                    fill={COLORS[index % COLORS.length]}
                  />
                ))}
              </Bar>
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
