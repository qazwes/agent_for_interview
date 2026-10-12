import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import { TooltipComponent, LegendComponent, GridComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { Presentation, Row } from "../types/agent";
echarts.use([BarChart, LineChart, PieChart, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer]);
export function QueryChart({ rows, presentation }: { rows: Row[]; presentation: Presentation }) {
  const ref = useRef<HTMLDivElement>(null);
  const spec = presentation.chart;
  const invalidPie = spec?.type === "pie" && rows.some(r => r[spec.metrics[0]] != null && Number(r[spec.metrics[0]]) < 0);
  useEffect(() => {
    if (!ref.current || !spec || invalidPie) return;
    const chart = echarts.init(ref.current);
    const fields = spec.metrics.map(key => presentation.columns.find(c => c.key === key)).filter(c => c !== undefined);
    const options: echarts.EChartsCoreOption = { color: ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4"], tooltip: { trigger: spec.type === "pie" ? "item" : "axis" }, legend: { bottom: 0 } };
    if (spec.type === "pie") {
      options.series = [{ type: "pie", radius: ["35%", "65%"], data: rows.filter(r => r[spec.metrics[0]] != null).map(r => ({ name: String(r[spec.dimension]), value: Number(r[spec.metrics[0]]) })), label: { formatter: "{b}: {d}%" } }];
    } else {
      const units = [...new Set(fields.map(c => c.unit))];
      options.grid = { top: 40, left: 65, right: units.length > 1 ? 65 : 30, bottom: 75, containLabel: true };
      options.xAxis = { type: "category", data: rows.map(r => String(r[spec.dimension])), axisLabel: { interval: 0, rotate: rows.length > 6 ? 25 : 0 } };
      options.yAxis = units.map((unit, i) => ({ type: "value", name: unit, position: i % 2 ? "right" : "left", offset: Math.floor(i / 2) * 50 }));
      options.series = fields.map(c => ({ name: c.label, type: spec.type, yAxisIndex: units.indexOf(c.unit), data: rows.map(r => r[c.key] == null ? null : Number(r[c.key])), barMaxWidth: 35 }));
    }
    chart.setOption(options);
    const observer = new ResizeObserver(() => chart.resize()); observer.observe(ref.current);
    return () => { observer.disconnect(); chart.dispose(); };
  }, [rows, presentation, spec, invalidPie]);
  if (!spec) return <p className="empty-note">本次结果没有适合绘图的维度与数值组合。</p>;
  if (invalidPie) return <p className="empty-note">结果包含负数，无法用饼图表达占比，请使用表格查看。</p>;
  return <div ref={ref} className="query-chart" role="img" aria-label={`查询结果${spec.type === "pie" ? "饼图" : spec.type === "line" ? "折线图" : "柱状图"}`} />;
}
