import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ToastContext, type ToastInput } from "./toast-context";

interface Item extends ToastInput {
  id: number;
}

/** Toasts from the reference: a single button; clicking opens the incident. Needs the router. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const next = useRef(1);
  const navigate = useNavigate();

  const push = useCallback((t: ToastInput) => {
    const id = next.current++;
    setItems((xs) => [...xs.slice(-3), { ...t, id }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 6500);
  }, []);

  const open = (t: Item) => {
    setItems((xs) => xs.filter((x) => x.id !== t.id));
    if (t.to) navigate(t.to);
  };

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => (
          <button key={t.id} type="button" className={`toast ${t.tone === "crit" ? "crit" : t.tone ?? ""}`.trim()} onClick={() => open(t)}>
            <strong>{t.title}</strong>
            {t.body && <span>{t.body}</span>}
          </button>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
