import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  failed: boolean;
}

/** Catches render errors so the console shows a message, not a blank page or a stack trace. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("UI render error", error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="m-8 max-w-lg rounded-lg border border-crit bg-crit-bg p-4 text-text">
        <h1 className="font-semibold">Something went wrong in the console</h1>
        <p className="mt-1 text-sm">The backend is not affected. Reloading the page usually fixes it.</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="mt-3 rounded-md border border-border bg-surface px-3 py-1.5 text-sm"
        >
          Reload
        </button>
      </div>
    );
  }
}
