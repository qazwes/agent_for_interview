import { formatValue } from "../lib/format";
import type { ResultColumn, Row } from "../types/agent";
export function ResultTable({ rows, columns = [] }: { rows: Row[]; columns?: ResultColumn[] }) {
  const keys = Array.from(new Set(rows.flatMap(row => Object.keys(row))));
  if (!rows.length) return <p className="empty-note">当前查询条件下没有数据。</p>;
  return <div className="table-scroll"><table className="data-table"><thead><tr>{keys.map(key => {
    const column = columns.find(c => c.key === key);
    return <th key={key}>{column?.label || key}{column?.unit && <span className="column-unit">（{column.unit}）</span>}</th>;
  })}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{keys.map(key => <td key={key}>{formatValue(row[key])}</td>)}</tr>)}</tbody></table></div>;
}
