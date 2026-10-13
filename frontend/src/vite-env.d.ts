/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  /** "true" serves sample incidents and audit events from src/lib/fixtures.ts */
  readonly VITE_USE_FIXTURES?: string;
}
