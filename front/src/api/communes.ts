import { apiGet } from "./client";
import type { CommuneSearchResponse } from "./types";

export function searchCommunes(
  q: string,
  limit = 10,
  signal?: AbortSignal,
): Promise<CommuneSearchResponse> {
  return apiGet<CommuneSearchResponse>("/communes/search", { q, limit }, signal);
}
