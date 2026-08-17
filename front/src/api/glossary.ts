import { apiGet } from "./client";
import type { GlossaryResponse } from "./types";

export function getGlossary(signal?: AbortSignal): Promise<GlossaryResponse> {
  return apiGet<GlossaryResponse>("/glossary", {}, signal);
}
