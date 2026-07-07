import type { ChunkingMode } from '../types';

const SENTENCE_BOUNDARY = /(?<=[.!?])\s+/;
const PARAGRAPH_BOUNDARY = /\n\s*\n+/;

function normalize(text: string): string {
  return text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
}

function splitSentences(text: string): string[] {
  return text
    .split(SENTENCE_BOUNDARY)
    .map((part) => part.trim())
    .filter(Boolean);
}

function splitAtWords(text: string, limit: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  if (words.some((word) => word.length > limit)) {
    // A single word exceeds the limit; the backend raises an error here,
    // but for preview purposes we just count it as one chunk.
    return words.filter((word) => word.length <= limit).concat(
      words.filter((word) => word.length > limit).map((word) => word.slice(0, limit)),
    );
  }
  const chunks: string[] = [];
  let current = '';
  for (const word of words) {
    const candidate = `${current} ${word}`.trim();
    if (candidate.length <= limit) {
      current = candidate;
    } else {
      if (current) chunks.push(current);
      current = word;
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

function pack(parts: string[], limit: number): string[] {
  const expanded: string[] = [];
  for (const part of parts) {
    expanded.push(...(part.length <= limit ? [part] : splitAtWords(part, limit)));
  }
  const chunks: string[] = [];
  let current = '';
  for (const part of expanded) {
    const candidate = `${current} ${part}`.trim();
    if (candidate.length <= limit) {
      current = candidate;
    } else {
      if (current) chunks.push(current);
      current = part;
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

export function countChunks(text: string, mode: ChunkingMode, characterLimit: number): number {
  if (characterLimit < 1) return 0;
  const normalized = normalize(text);
  if (!normalized) return 0;

  if (mode === 'whole') return 1;

  if (mode === 'line') {
    return normalized.split('\n').map((line) => line.trim()).filter(Boolean).length;
  }

  if (mode === 'paragraph') {
    return normalized.split(PARAGRAPH_BOUNDARY).map((part) => part.trim()).filter(Boolean).length;
  }

  if (mode === 'sentence') {
    return splitSentences(normalized).length;
  }

  // character mode
  return pack(splitSentences(normalized), characterLimit).length;
}
