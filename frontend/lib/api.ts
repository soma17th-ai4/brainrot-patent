import type { GenerateRequest, GenerateResponse } from "./types";
export type { GenerateRequest, GenerateResponse } from "./types";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function generatePatent(
  request: GenerateRequest,
): Promise<GenerateResponse> {
  const response = await fetch(`${BACKEND_URL}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Generate request failed: ${response.status}`);
  }
  return response.json();
}
