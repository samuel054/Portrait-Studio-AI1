export type AnalysisResponse = {
  filename: string | null;
  analysis: { width: number; height: number; megapixels: number; blur_level: string; lighting: string; needs_enhancement: boolean };
  identity: { face_count: number; identity_readiness: string; identity_risk: string; guidance: string[] };
  next_step: string;
};
export type PortraitStyle = {
  id: string; name: string; category: string; description: string; identity_priority: string;
  pose_preservation: boolean; clothing_preservation: boolean; background_modes: string[]; output_types: string[];
};
export type PortraitOptions = { crop: string; background: string; output_type: string; candidate_count: number };
export type PortraitJob = {
  id: string; status: string; stage: string; style_id: string; candidate_session_id?: string | null;
  error?: { code: string; message: string } | null;
};
export type CandidatePreview = {
  id: string; rank: number; score: number; status: string; recommended: boolean;
  filename: string; content_type: string; image_base64: string; reasons: string[];
};
export type CandidateSession = { id: string; status: string; selected_candidate_id: string | null; candidates: CandidatePreview[] };
export type RenderResult = { filename: string; content_type: string; width: number; height: number; image_base64: string };
export type ExportOptions = { output_format: string; max_dimension: number | null };
export type RuntimeStatus = { ready: boolean; background_removal: boolean; checks: { id: string; ready: boolean; message: string }[] };
const API = "/api/backend";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, { cache: "no-store", ...init });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg ?? "Invalid option").join(". ")
      : `The request failed (${response.status}). Please try again.`;
    throw new Error(message);
  }
  return payload as T;
}
const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const getRuntime = () => request<RuntimeStatus>("/v1/runtime");
export async function getStyles(): Promise<PortraitStyle[]> {
  return (await request<{ styles: PortraitStyle[] }>("/v1/styles")).styles;
}
export function analyzePhoto(file: File): Promise<AnalysisResponse> {
  const body = new FormData(); body.append("file", file);
  return request("/v1/analyze", { method: "POST", body });
}
export async function createPortraitJob(file: File, styleId: string, options: PortraitOptions): Promise<PortraitJob> {
  const body = new FormData();
  body.append("file", file); body.append("style_id", styleId);
  Object.entries(options).forEach(([key, value]) => body.append(key, String(value)));
  body.append("preserve_pose", "true"); body.append("preserve_clothing", "true");
  return (await request<{ job: PortraitJob }>("/v1/portrait-jobs", { method: "POST", body })).job;
}
export async function getPortraitJob(id: string): Promise<PortraitJob> {
  return (await request<{ job: PortraitJob }>(`/v1/portrait-jobs/${encodeURIComponent(id)}`)).job;
}
export async function getCandidateSession(id: string): Promise<CandidateSession> {
  return (await request<{ session: CandidateSession }>(`/v1/candidate-sessions/${encodeURIComponent(id)}`)).session;
}
export async function selectCandidate(id: string, candidateId: string): Promise<CandidateSession> {
  return (await request<{ session: CandidateSession }>(`/v1/candidate-sessions/${encodeURIComponent(id)}/selection`, json({ candidate_id: candidateId }))).session;
}
export async function refineCandidate(id: string, styleId: string, operation: string, instruction: string, options: PortraitOptions): Promise<PortraitJob> {
  return (await request<{ job: PortraitJob }>(`/v1/candidate-sessions/${encodeURIComponent(id)}/refine`, json({
    ...options, style_id: styleId, operation, instruction, strength: 0.2, candidate_count: 2,
  }))).job;
}
export async function renderCandidate(id: string, options: ExportOptions): Promise<RenderResult> {
  return (await request<{ render: RenderResult }>(`/v1/candidate-sessions/${encodeURIComponent(id)}/render`, json({ ...options, quality: 95, allow_upscale: false }))).render;
}
export async function submitFeedback(id: string, candidateId: string, rating: number, accepted: boolean, comment: string): Promise<void> {
  await request(`/v1/candidate-sessions/${encodeURIComponent(id)}/feedback`, json({ candidate_id: candidateId, rating, accepted, reasons: [], comment: comment || null }));
}
