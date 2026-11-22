export type Tab = 'ask' | 'summary' | 'cards';

export interface Note {
  name: string;
  chunks: number;
}

/** A retrieved piece of a note that the answer is based on. */
export interface Passage {
  source: string;
  /** cosine similarity 0..1; 0 means it was found by keyword search only */
  score: number;
  text: string;
}

export interface Flashcard {
  question: string;
  answer: string;
}

export interface UploadResult {
  name: string;
  chunks: number;
  error: string | null;
}

export interface Health {
  status: string;
  model: string;
  local: boolean;
  chunks: number;
  formats: string[];
}

export interface AskResponse {
  answer: string;
  sources: Passage[];
}

export interface SummaryResponse {
  summary: string;
  sources: string[];
}

export interface FlashcardsResponse {
  cards: Flashcard[];
}

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  text: string;
  sources: Passage[];
  error: boolean;
}

export interface Toast {
  id: number;
  kind: 'error' | 'success' | 'info';
  text: string;
}
