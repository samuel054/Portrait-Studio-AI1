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

type StylesResponse = {
  count: number;
  styles: PortraitStyle[];
};

const API_BASE = "/api/backend";

async function readError(response: Response, fallback: string): Promise<Error> {
  const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
  return new Error(payload?.detail ?? fallback);
}

export async function analyzePhoto(file: File): Promise<AnalysisResponse> {
  const body = new FormData();
  body.append("file", file);

  const response = await fetch(`${API_BASE}/v1/analyze`, {
    method: "POST",
    body,
  });

  if (!response.ok) {
    throw await readError(response, "We could not analyze this photo.");
  }

  return response.json() as Promise<AnalysisResponse>;
}

export async function getStyles(): Promise<PortraitStyle[]> {
  const response = await fetch(`${API_BASE}/v1/styles`, { cache: "no-store" });
  if (!response.ok) {
    throw await readError(response, "We could not load portrait styles.");
  }
  const payload = (await response.json()) as StylesResponse;
  return payload.styles;
}
