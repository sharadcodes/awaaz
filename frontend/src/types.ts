export type ChunkingMode = 'paragraph' | 'line' | 'sentence' | 'character' | 'whole';
export type JobAction = 'pause' | 'resume' | 'cancel';

export interface Backend {
  name: string;
  base_url: string;
  model: string;
  voice: string;
  max_characters: number;
}

export interface Document {
  id: string;
  title: string;
  source_filename: string | null;
  text: string;
  revision: number;
  author: string | null;
  series: string | null;
  tags: string | null;
  cover_path: string | null;
  metadata_json: Record<string, unknown> | null;
  word_count: number;
  created_at: string;
  updated_at: string;
  collection_names: string[];
}

export interface Collection {
  id: string;
  name: string;
  document_count: number;
  created_at: string;
  updated_at: string;
}

export interface Progress {
  total: number;
  completed: number;
  failed: number;
  processed: number;
  percent: number;
}

export interface Job {
  id: string;
  document_id: string;
  document_revision: number;
  status: string;
  backend: string;
  model: string;
  voice: string;
  speed: number;
  chunking_mode: string;
  character_limit: number;
  error: string | null;
  output_available: boolean;
  progress: Progress;
  created_at: string;
  updated_at: string;
}

export interface JobRequest {
  backend: string;
  model: string;
  voice: string;
  speed: number;
  chunking_mode: ChunkingMode;
  character_limit: number;
}
