import { useEffect, useState } from "react";
import { ApiError } from "../api/client";

/**
 * The four states every screen in docs/13 has to render.
 *
 * Modelled as a discriminated union rather than a bag of booleans so that
 * "loading and error at the same time" cannot be represented, and so a
 * component is forced by the compiler to handle the empty and error cases
 * rather than rendering `undefined` into the page.
 */
export type ApiResource<T> =
  | { state: "loading" }
  | { state: "success"; data: T }
  | { state: "error"; error: ApiError | Error };

/**
 * Fetch once per change of `key`, with in-flight requests aborted.
 *
 * Deliberately not a caching library: reads here are simple, and the backend
 * already owns the only caching this product does (validated interpretations).
 * A client-side cache would duplicate a concern that was kept server-side on
 * purpose.
 *
 * `key` is what identifies the request — when it changes the previous fetch is
 * aborted, which is what stops a slow earlier response from overwriting a
 * newer one after the user has typed again.
 */
export function useApiResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  key: string,
): ApiResource<T> {
  const [resource, setResource] = useState<ApiResource<T>>({ state: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    setResource({ state: "loading" });

    fetcher(controller.signal)
      .then((data) => {
        if (active) setResource({ state: "success", data });
      })
      .catch((error: unknown) => {
        // An abort is not a failure — it means we deliberately moved on.
        if (controller.signal.aborted || !active) return;
        setResource({
          state: "error",
          error: error instanceof Error ? error : new Error(String(error)),
        });
      });

    return () => {
      active = false;
      controller.abort();
    };
    // `fetcher` is recreated on every render by design; `key` is what decides
    // when a refetch is actually warranted.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return resource;
}
