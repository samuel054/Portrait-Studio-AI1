export type AnalysisResponse = {
  filename: string | null;
  analysis: {
    width: number;
    height: number;
    megapixels: number;
    blur_level: string;
    lighting: string;
    needs_enhancement: boolean;
  };
  identity: {
    face_count: number;
    identity_readiness: string;
    risk_level: string;
  };
  next_step: string;
};

export type PortraitStyle = {
  id: string;
  name: string;
  category: string;
  description: string;
  identity_priority: string;
  pose_preservation: boolean;
  clothing_preservation: boolean;
  background_modes: string[];
  output_types: string[];
};

export type PortraitJob = {
  id: string;
  status: string;
  stage: string;
  progress: number;
  style_id: string;
  prompt_id?: string | null;
  candidate_session_id?: string | null;
  error_code?: string | null;
  error_message?: string | null;
};

export type CandidatePreview = {
  id: string;
  source_index: number;
  rank: number;
  score: number;
  status: string;
  recommended: boolean;
  filename: string;
  content_type: string;
  image_base64: string;
  reasons: string[];
};

export type CandidateSession = {
  id: string;
  prompt_id: string;
  status: string;
  selected_candidate_id: string | null;
  candidates: CandidatePreview[];
};

export type RenderResult = {
  filename: string;
  content_type: string;
  width: number;
  height: number;
  image_base64: string;
};

export type GenerationImage = {
  filename: string;
  subfolder: string;
  image_type: string;
  content_type: string;
  image_base64: string;
};

export type GenerationResult = {
  prompt_id: string;
  status: string;
  images: GenerationImage[];
  error: string | null;
};

type StylesResponse = { count: number; styles: PortraitStyle[] };
type JobResponse = { job: PortraitJob; next_step: string };
type CandidateSessionResponse = { session: CandidateSession };

const API_BASE = "/api/backend";

async function readError(response: Response, fallback: string): Promise<Error> {
  const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
  return new Error(payload?.detail ?? fallback);
}

export async function analyzePhoto(file: File): Promise<AnalysisResponse> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${API_BASE}/v1/analyze`, { method: "POST", body });
  if (!response.ok) throw await readError(response, "We could not analyze this photo.");
  return response.json() as Promise<AnalysisResponse>;
}

export async function getStyles(): Promise<PortraitStyle[]> {
  const response = await fetch(`${API_BASE}/v1/styles`, { cache: "no-store" });
  if (!response.ok) throw await readError(response, "We could not load portrait styles.");
  const payload = (await response.json()) as StylesResponse;
  return payload.styles;
}

export async function createPortraitJob(file: File, styleId: string): Promise<PortraitJob> {
  const body = new FormData();
  body.append("file", file);
  body.append("style_id", styleId);
  body.append("crop", "original");
  body.append("background", "keep");
  body.append("output_type", "social");
  body.append("preserve_pose", "true");
  body.append("preserve_clothing", "true");
  body.append("candidate_count", "4");
  const response = await fetch(`${API_BASE}/v1/portrait-jobs`, { method: "POST", body });
  if (!response.ok) throw await readError(response, "We could not start portrait generation.");
  return ((await response.json()) as JobResponse).job;
}

export async function getPortraitJob(jobId: string, refresh = true): Promise<PortraitJob> {
  const response = await fetch(`${API_BASE}/v1/portrait-jobs/${encodeURIComponent(jobId)}?refresh=${refresh ? "true" : "false"}`, { cache: "no-store" });
  if (!response.ok) throw await readError(response, "We could not refresh this portrait job.");
  return ((await response.json()) as JobResponse).job;
}

export async function getCandidateSession(sessionId: string): Promise<CandidateSession> {
  const response = await fetch(`${API_BASE}/v1/candidate-sessions/${encodeURIComponent(sessionId)}?include_images=true`, { cache: "no-store" });
  if (!response.ok) throw await readError(response, "We could not load generated portraits.");
  return ((await response.json()) as CandidateSessionResponse).session;
}

export async function selectCandidate(sessionId: string, candidateId: string): Promise<CandidateSession> {
  const response = await fetch(`${API_BASE}/v1/candidate-sessions/${encodeURIComponent(sessionId)}/selection`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_id: candidateId }),
  });
  if (!response.ok) throw await readError(response, "We could not save your portrait selection.");
  return ((await response.json()) as CandidateSessionResponse).session;
}

export async function submitFeedback(sessionId: string, candidateId: string, rating: number, accepted: boolean, comment?: string): Promise<void> {
  const response = await fetch(`${API_BASE}/v1/candidate-sessions/${encodeURIComponent(sessionId)}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_id: candidateId, rating, accepted, reasons: [], comment: comment || null }),
  });
  if (!response.ok) throw await readError(response, "We could not save your feedback.");
}

export async function refineCandidate(sessionId: string, styleId: string, operation: string, instruction: string): Promise<GenerationResult> {
  const response = await fetch(`${API_BASE}/v1/candidate-sessions/${encodeURIComponent(sessionId)}/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      style_id: styleId,
      operation,
      instruction,
      crop: "original",
      background: "keep",
      output_type: "social",
      preserve_pose: true,
      preserve_clothing: true,
      strength: 0.2,
      candidate_count: 2,
    }),
  });
  if (!response.ok) throw await readError(response, "We could not start refinement.");
  const payload = (await response.json()) as { generation: GenerationResult };
  return payload.generation;
}

export async function getGeneration(promptId: string): Promise<GenerationResult> {
  const response = await fetch(`${API_BASE}/v1/generations/${encodeURIComponent(promptId)}?include_images=true`, { cache: "no-store" });
  if (!response.ok) throw await readError(response, "We could not refresh the refinement.");
  const payload = (await response.json()) as { generation: GenerationResult };
  return payload.generation;
}

export async function renderCandidate(sessionId: string): Promise<RenderResult> {
  const response = await fetch(`${API_BASE}/v1/candidate-sessions/${encodeURIComponent(sessionId)}/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ output_format: "png", quality: 95, allow_upscale: false }),
  });
  if (!response.ok) throw await readError(response, "We could not render the selected portrait.");
  const payload = (await response.json()) as { render: RenderResult };
  return payload.render;
}
