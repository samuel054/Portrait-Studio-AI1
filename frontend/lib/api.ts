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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function analyzePhoto(file: File): Promise<AnalysisResponse> {
  const body = new FormData();
  body.append("file", file);

  const response = await fetch(`${API_BASE}/v1/analyze`, {
    method: "POST",
    body,
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "We could not analyze this photo.");
  }

  return response.json() as Promise<AnalysisResponse>;
}
