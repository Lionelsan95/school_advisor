/**
 * The single place the frontend talks to the API.
 *
 * The base URL comes from the environment, never from a literal: the app runs
 * against a different host in dev and in deployment, and hardcoding one is the
 * frontend equivalent of the rule the backend's Definition of Done (§5)
 * already enforces for settings.
 */

/**
 * Where the API lives, from the environment.
 *
 * The localhost fallback applies **in development only**. It used to be
 * unconditional, which meant a production build made without
 * `VITE_API_BASE_URL` would ship pointing at the visitor's own machine: every
 * request fails, and it looks like the visitor's problem rather than a
 * misbuilt image. That is precisely the failure mode the backend avoids by
 * giving `DATABASE_URL` no default — a missing setting should fail loudly at
 * the boundary, not quietly produce a broken product.
 *
 * `import.meta.env.DEV` is replaced at build time, so the throw below is the
 * only branch left in a production bundle.
 */
function resolveBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (configured) return configured;
  if (import.meta.env.DEV) return "http://localhost:8000";
  throw new Error(
    "VITE_API_BASE_URL must be set at build time. Vite inlines it into the " +
      "bundle, so it cannot be supplied at runtime.",
  );
}

const BASE_URL: string = resolveBaseUrl();

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
