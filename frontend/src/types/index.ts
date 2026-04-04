// Document types
export type DocumentStatus = "pending" | "processing" | "indexed" | "failed";

export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  file_path: string;
  file_type: string;
  file_size: number;
  status: DocumentStatus;
  chunk_count: number;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface DocumentListResponse {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  documents: Document[];
}

export interface DocumentUploadResponse {
  upload_id: string;
  document: Document;
  message: string;
}

export interface DocumentIngestResponse {
  document_id: string;
  status: DocumentStatus;
  chunk_count: number;
  message: string;
}

// Chat types
export interface SourceDocument {
  source: string;
  document_id: string;
  chunk_index: number;
  similarity_score: number;
  content_preview: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  include_sources?: boolean;
  k?: number;
}

export interface ChatResponse {
  answer: string;
  sources: SourceDocument[];
  session_id: string;
  metadata: Record<string, unknown>;
}

export interface StreamEvent {
  event: "retrieval" | "token" | "sources" | "done" | "error";
  data: string | SourceDocument[] | null;
}

// Conversation types
export type MessageRole = "user" | "assistant" | "system";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface Conversation {
  id: string;
  messages: Message[];
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
}

export interface ConversationListResponse {
  total: number;
  page: number;
  page_size: number;
  pages: number;
  conversations: Conversation[];
}

// Health check
export interface HealthResponse {
  status: string;
  version: string;
  environment: string;
  timestamp: string;
}
