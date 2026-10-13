import { useCallback, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ToastContext, type ToastInput } from "./toast-context";

interface Item extends ToastInput {
  id: number;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const next = useRef(1);

  const dismiss = (id: number) => setItems((xs) => xs.filter((x) => x.id !== id));
  const push = useCallback((t: ToastInput) => {
    const id = next.current++;
    setItems((xs) => [...xs.slice(-3), { ...t, id }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 8000);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div role="status" aria-live="polite" className="fixed right-4 bottom-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            className={`rounded-lg border bg-surface p-3 shadow-lg ${t.tone === "crit" ? "border-crit" : "border-border"}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="text-sm font-semibold">
                {t.tone === "crit" && <span aria-hidden="true">✕ </span>}
                {t.title}
              </div>
              <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss" className="text-muted hover:text-text">
                ×
              </button>
            </div>
            {t.body && <p className="mt-1 text-sm text-muted">{t.body}</p>}
            {t.to && (
              <Link to={t.to} onClick={() => dismiss(t.id)} className="mt-2 inline-block text-sm text-accent underline">
                Open incident
              </Link>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
