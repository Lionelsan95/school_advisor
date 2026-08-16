import { apiGet } from "./client";
import type {
  CompareResponse,
  FactSheet,
  HistoryResponse,
  SearchParams,
  SearchResponse,
} from "./types";

export function searchEstablishments(
  params: SearchParams,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  return apiGet<SearchResponse>("/establishments/search", { ...params }, signal);
}

export function getFactSheet(uai: string, signal?: AbortSignal): Promise<FactSheet> {
  return apiGet<FactSheet>(`/establishments/${encodeURIComponent(uai)}`, {}, signal);
}

export function getHistory(uai: string, signal?: AbortSignal): Promise<HistoryResponse> {
  return apiGet<HistoryResponse>(
    `/establishments/${encodeURIComponent(uai)}/history`,
    {},
    signal,
  );
}

export function compareEstablishments(
  uais: string[],
  signal?: AbortSignal,
): Promise<CompareResponse> {
  const query = uais.map((uai) => `uai=${encodeURIComponent(uai)}`).join("&");
  return apiGet<CompareResponse>(`/establishments/compare?${query}`, {}, signal);
}
