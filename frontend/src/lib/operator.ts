const KEY = "loopwatch.operator";

/** The operator name recorded with approvals. Authentication is out of scope. */
export function getOperator(): string {
  try {
    return localStorage.getItem(KEY) || "operator";
  } catch {
    return "operator";
  }
}

export function setOperator(name: string): void {
  try {
    localStorage.setItem(KEY, name);
  } catch {
    /* storage unavailable: the name just won't persist */
  }
}
