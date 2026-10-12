import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";
export function Modal({ title, onClose, children, footer, wide = false }: {
  title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  const id = useId();
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeRef.current();
      if (event.key === "Tab") {
        const list = Array.from(ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input, textarea, select, [tabindex="0"]') ?? []);
        const first = list[0], last = list[list.length - 1];
        if (event.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener("keydown", handler);
    return () => { document.removeEventListener("keydown", handler); previous?.focus(); };
  }, []);
  return <div className="modal-overlay" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
    <div ref={ref} tabIndex={-1} className={`modal${wide ? " wide" : ""}`} role="dialog" aria-modal="true" aria-labelledby={id}>
      <header><h3 id={id}>{title}</h3><button className="icon-button" aria-label="关闭弹窗" onClick={onClose}><X size={19} /></button></header>
      <div className="modal-body">{children}</div>{footer && <footer>{footer}</footer>}
    </div>
  </div>;
}
