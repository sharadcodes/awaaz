import type { Backend, Collection, Document, Job, JobAction, JobRequest } from '../types';

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new ApiError(
      body.detail ?? `Request failed with status ${response.status}`,
      response.status,
    );
  }
  // 204 No Content (and any empty body) has nothing to parse.
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

const jsonHeaders = { 'Content-Type': 'application/json' };

export function listBackends(): Promise<Backend[]> {
  return request('/api/v1/backends');
}

export function listDocuments(params?: {
  collection_id?: string;
  author?: string;
  series?: string;
  tag?: string;
}): Promise<Document[]> {
  const search = new URLSearchParams();
  if (params?.collection_id) search.append('collection_id', params.collection_id);
  if (params?.author) search.append('author', params.author);
  if (params?.series) search.append('series', params.series);
  if (params?.tag) search.append('tag', params.tag);
  const query = search.toString();
  return request(`/api/v1/documents${query ? `?${query}` : ''}`);
}

export function listCollections(): Promise<Collection[]> {
  return request('/api/v1/collections');
}

export function createCollection(name: string): Promise<Collection> {
  return request('/api/v1/collections', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ name }),
  });
}

export function updateCollection(
  collectionId: string,
  updates: { name?: string; document_ids?: string[] },
): Promise<Collection> {
  return request(`/api/v1/collections/${collectionId}`, {
    method: 'PUT',
    headers: jsonHeaders,
    body: JSON.stringify(updates),
  });
}

export function deleteCollection(collectionId: string): Promise<void> {
  return request(`/api/v1/collections/${collectionId}`, { method: 'DELETE' });
}

export function getCoverUrl(documentId: string): string {
  return `/api/v1/documents/${documentId}/cover`;
}

export function listBackendVoices(name: string): Promise<{ backend: string; voices: string[] }> {
  return request(`/api/v1/backends/${name}/voices`);
}

export function createTextDocument(title: string, text: string): Promise<Document> {
  return request('/api/v1/documents', {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify({ title, text }),
  });
}

export function uploadDocument(file: File, title?: string): Promise<Document> {
  const body = new FormData();
  body.append('file', file);
  if (title) body.append('title', title);
  return request('/api/v1/documents/upload', { method: 'POST', body });
}

export function updateDocument(document: Document, text: string): Promise<Document> {
  return request(`/api/v1/documents/${document.id}/text`, {
    method: 'PUT',
    headers: jsonHeaders,
    body: JSON.stringify({ text, expected_revision: document.revision }),
  });
}

export function deleteDocument(documentId: string): Promise<void> {
  return request(`/api/v1/documents/${documentId}`, { method: 'DELETE' });
}

export function listJobs(): Promise<Job[]> {
  return request('/api/v1/jobs');
}

export function createJob(documentId: string, settings: JobRequest): Promise<Job> {
  return request(`/api/v1/documents/${documentId}/jobs`, {
    method: 'POST',
    headers: jsonHeaders,
    body: JSON.stringify(settings),
  });
}

export function controlJob(jobId: string, action: JobAction): Promise<Job> {
  return request(`/api/v1/jobs/${jobId}/${action}`, { method: 'POST' });
}
