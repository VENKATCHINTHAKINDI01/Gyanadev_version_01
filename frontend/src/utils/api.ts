/// <reference types="vite/client" />
import axios from "axios";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const api = axios.create({ baseURL: BASE, timeout: 30000 });

// Auto-attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("gyanadeva_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-logout on 401
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.clear();
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// ── Types ──────────────────────────────────────────────────────────

export interface Student {
  student_id: string;
  name: string;
  email: string;
  age: number;
  preferred_language: string;
  preferred_voice: string;
  last_book: string | null;
  last_topic: string | null;
  last_character: string | null;
  scores: {
    knowledge: number;
    enthusiasm: number;
    pronunciation: number;
    total_interactions: number;
  };
  streak: number;
}

export interface AskResponse {
  answer: string;
  sources: string[];
  language: string;
  is_grounded: boolean;
  faithfulness_score: number;
  pronunciation_correction: string | null;
  latency_ms: Record<string, number>;
}

export interface WelcomeResponse {
  message: string | null;
  is_returning: boolean;
  student_name: string;
  last_book: string | null;
  last_topic: string | null;
  streak: number;
}

export interface Progress {
  knowledge_score: number;
  enthusiasm_score: number;
  pronunciation_score: number;
  total_interactions: number;
  streak_days: number;
  teaching_level: "beginner" | "intermediate" | "advanced";
}

export interface PronunciationHistory {
  common_errors: { word: string; correct: string; count: number }[];
  total_corrections: number;
}

export type BookFilter = "mahabharata" | "ramayana" | "bhagavad_gita" | null;

// ── Auth ───────────────────────────────────────────────────────────

export async function register(data: {
  name: string;
  email: string;
  password: string;
  age: number;
  preferred_language: string;
}) {
  const { data: res } = await api.post("/auth/register", data);
  localStorage.setItem("gyanadeva_token", res.access_token);
  localStorage.setItem("gyanadeva_student_id", res.student_id);
  localStorage.setItem("gyanadeva_name", res.name);
  return res;
}

export async function login(email: string, password: string) {
  const { data: res } = await api.post("/auth/login", { email, password });
  localStorage.setItem("gyanadeva_token", res.access_token);
  localStorage.setItem("gyanadeva_student_id", res.student_id);
  localStorage.setItem("gyanadeva_name", res.name);
  return res;
}

export function logout() {
  localStorage.clear();
  window.location.href = "/login";
}

export function getStoredName() {
  return localStorage.getItem("gyanadeva_name") || "";
}

export function isLoggedIn() {
  return !!localStorage.getItem("gyanadeva_token");
}

// ── Student ────────────────────────────────────────────────────────

export async function getProfile(): Promise<Student> {
  const { data } = await api.get("/api/v1/student/profile");
  return data;
}

export async function getProgress(): Promise<Progress> {
  const { data } = await api.get("/api/v1/student/progress");
  return data;
}

export async function getPronunciationHistory(): Promise<PronunciationHistory> {
  const { data } = await api.get("/api/v1/student/pronunciation");
  return data;
}

export async function updatePreferences(prefs: {
  preferred_language?: string;
  preferred_voice?: string;
}) {
  const { data } = await api.patch("/api/v1/student/preferences", prefs);
  return data;
}

// ── Guru ───────────────────────────────────────────────────────────

export async function askGuru(
  question: string,
  language = "auto",
  bookFilter: BookFilter = null
): Promise<AskResponse> {
  const { data } = await api.post("/api/v1/guru/ask", {
    question,
    language,
    book_filter: bookFilter,
  });
  return data;
}

export async function getWelcome(): Promise<WelcomeResponse> {
  const { data } = await api.get("/api/v1/guru/welcome");
  return data;
}

export function streamAsk(
  question: string,
  language: string,
  bookFilter: BookFilter,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (e: Error) => void
): () => void {
  const ctrl = new AbortController();
  const token = localStorage.getItem("gyanadeva_token");

  fetch(`${BASE}/api/v1/guru/ask/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ question, language, book_filter: bookFilter }),
    signal: ctrl.signal,
  })
    .then(async (res) => {
      const reader = res.body?.getReader();
      const dec = new TextDecoder();
      if (!reader) return;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        for (const line of dec.decode(value).split("\n")) {
          if (!line.startsWith("data: ")) continue;
          const d = line.slice(6);
          if (d === "[DONE]") { onDone(); return; }
          onChunk(d);
        }
      }
      onDone();
    })
    .catch((e) => { if (e.name !== "AbortError") onError(e); });

  return () => ctrl.abort();
}

// ── Audio ──────────────────────────────────────────────────────────

export async function transcribeAudio(blob: Blob, language = "auto") {
  const form = new FormData();
  form.append("audio", blob, "audio.webm");
  form.append("language", language);
  const { data } = await api.post("/api/v1/audio/transcribe", form);
  return data as { text: string; detected_language: string };
}

export async function speakText(text: string, language: string): Promise<Blob> {
  const form = new FormData();
  form.append("text", text);
  form.append("language", language);
  const { data } = await api.post("/api/v1/audio/speak", form, {
    responseType: "blob",
  });
  return data;
}