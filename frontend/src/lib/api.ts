const BASE = import.meta.env.VITE_API_BASE ?? "";

export const apiUrl = (path: string): string => `${BASE}/api/v1${path}`;

const TIMEOUT_MS = 10_000;

async function request(url: string, init?: RequestInit): Promise<Response> {
  return fetch(url, { ...init, signal: AbortSignal.timeout(TIMEOUT_MS) });
}

export async function apiGet<T>(path: string): Promise<T> {
  if (import.meta.env.VITE_USE_FIXTURES === "true") {
    const { fixtureFor } = await import("./fixtures");
    const fixture = fixtureFor(path.split("?")[0]);
    if (fixture !== undefined) return fixture as T;
  }
  // One retry for reads: a dropped request should not blank a page.
  let res: Response;
  try {
    res = await request(apiUrl(path));
  } catch {
    res = await request(apiUrl(path));
  }
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await request(apiUrl(path), {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const res = await request(apiUrl(path), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(detail?.detail ?? `PUT ${path} failed: ${res.status}`);
  }
  return (await res.json()) as T;
}
