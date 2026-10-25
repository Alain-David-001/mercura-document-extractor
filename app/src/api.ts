export type JobStatus = "queued" | "processing" | "completed" | "failed";
export interface DocumentRecord {
  id: string;
  filename: string;
  size_bytes: number;
  page_count: number;
  project_id: string | null;
  project_name: string | null;
  ai_project_id: string | null;
  ai_project_name: string | null;
  warning: string | null;
  revision: number;
  created_at: string;
  updated_at: string;
  job: {
    status: JobStatus;
    phase: string;
    attempts: number;
    completed_chunks: number;
    total_chunks: number;
    error: string | null;
    updated_at: string;
  };
}
export interface CommentRecord {
  id: string;
  text: string;
  created_at: string;
}
export interface DocumentDetail extends DocumentRecord {
  comments: CommentRecord[];
}

export interface WorkerAvailability {
  available: boolean;
  last_seen_at: string | null;
}

export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, options);
  } catch {
    throw new Error(
      "Cannot reach the server. Check that the backend is running and try again.",
    );
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail: unknown = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((item: { msg?: string }) => item.msg || "Invalid input")
              .join(". ")
          : `Request failed (${response.status}). Please try again.`;
    throw new Error(message);
  }
  return payload as T;
}

export function jsonBody(value: unknown): RequestInit {
  return {
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(value),
  };
}
