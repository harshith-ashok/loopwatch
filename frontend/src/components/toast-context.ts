import { createContext, useContext } from "react";

export interface ToastInput {
  title: string;
  body?: string;
  to?: string;
  tone?: "info" | "crit";
}

export const ToastContext = createContext<(t: ToastInput) => void>(() => {});
export const useToast = () => useContext(ToastContext);
