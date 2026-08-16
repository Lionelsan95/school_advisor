/**
 * The single place the frontend talks to the API.
 *
 * The base URL comes from the environment, never from a literal: the app runs
 * against a different host in dev and in deployment, and hardcoding one is the
 * frontend equivalent of the rule the backend's Definition of Done (§5)
 * already enforces for settings.
 */

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/**
 * A failed request, carrying the distinction the API contract makes.
 *
 * These statuses mean different things here and the UI must be able to tell
 * them apart: 404 is "no record of this establishment", 400 is "that is not a
 * valid identifier", and 503 is "we hold official data but cannot show its
 * provenance, so we are withholding it" — which is a deliberate editorial
 * choice, not a crash, and must be explained as such rather than shown as a
 * generic error.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string | null;

  constructor(status: number, detail: string | null) {
    super(detail ?? `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }

  /** The establishment or commune simply is not in the reference data. */
  get isNotFound(): boolean {
    return this.status === 404;
  }

  /** The request itself was malformed — a bad UAI, or a refused sort parameter. */
  get isBadRequest(): boolean {
    return this.status === 400 || this.status === 422;
  }

  /**
   * Data exists but its provenance does not, so the API withheld it.
   * Never present this as a failure of the establishment.
   */
  get isProvenanceWithheld(): boolean {
    return this.status === 503;
  }
}

async function parseDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : null;
  } catch {
    return null;
  }
}

export async function apiGet<T>(
  path: string,
  params: Record<string, string | number | undefined> = {},
  signal?: AbortSignal,
): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  const response = await fetch(url, { signal, headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new ApiError(response.status, await parseDetail(response));
  }
  return (await response.json()) as T;
}
