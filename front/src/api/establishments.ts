import { apiGet } from "./client";
import type { FactSheet, SearchParams, SearchResponse } from "./types";

export function searchEstablishments(
  params: SearchParams,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  return apiGet<SearchResponse>("/establishments/search", { ...params }, signal);
}

export function getFactSheet(uai: string, signal?: AbortSignal): Promise<FactSheet> {
  return apiGet<FactSheet>(`/establishments/${encodeURIComponent(uai)}`, {}, signal);
}
