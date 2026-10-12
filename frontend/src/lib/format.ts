export function formatValue(value: unknown) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}
export function formatDate(value: string) { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }
export function errorText(error: unknown) { return error instanceof Error ? error.message : String(error); }
export async function copyText(text: string) { await navigator.clipboard.writeText(text); }
