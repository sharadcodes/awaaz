import { useEffect, useMemo, useState } from 'react';

import { listBackendVoices } from '../api/client';
import type { Backend, ChunkingMode, JobRequest } from '../types';

interface GenerationFormProps {
  backends: Backend[];
  disabled: boolean;
  onSubmit: (settings: JobRequest) => void;
}

const modes: { value: ChunkingMode; label: string; detail: string }[] = [
  { value: 'paragraph', label: 'Paragraphs', detail: 'Natural narration flow' },
  { value: 'sentence', label: 'Sentences', detail: 'Precise recovery points' },
  { value: 'line', label: 'Lines', detail: 'Respect source line breaks' },
  { value: 'character', label: 'Character limit', detail: 'Pack sentences safely' },
  { value: 'whole', label: 'Whole text', detail: 'One request when supported' },
];

function modeDetail(value: ChunkingMode): string {
  return modes.find((item) => item.value === value)?.detail ?? '';
}

export function GenerationForm({ backends, disabled, onSubmit }: GenerationFormProps) {
  const [backendName, setBackendName] = useState('');
  const [model, setModel] = useState('');
  const [voice, setVoice] = useState('');
  const [speed, setSpeed] = useState(1);
  const [mode, setMode] = useState<ChunkingMode>('paragraph');
  const [characterLimit, setCharacterLimit] = useState(1000);
  const [voices, setVoices] = useState<string[]>([]);

  const backend = useMemo(
    () => backends.find((item) => item.name === backendName) ?? backends[0],
    [backendName, backends],
  );

  useEffect(() => {
    if (!backend) return;
    setBackendName(backend.name);
    setModel(backend.model);
    setVoice(backend.voice);
    setCharacterLimit((current) => Math.min(current, backend.max_characters));
  }, [backend]);

  useEffect(() => {
    if (!backend) return;
    let cancelled = false;
    listBackendVoices(backend.name)
      .then((response) => {
        if (cancelled) return;
        const all = Array.from(new Set([backend.voice, ...response.voices]));
        setVoices(all);
      })
      .catch(() => {
        if (!cancelled) setVoices([backend.voice]);
      });
    return () => {
      cancelled = true;
    };
  }, [backend]);

  if (!backend) return <p className="empty-state">No TTS backend configured.</p>;

  return (
    <form
      className="generation-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({
          backend: backend.name,
          model,
          voice,
          speed,
          chunking_mode: mode,
          character_limit: characterLimit,
        });
      }}
    >
      <div className="field-grid">
        <label>
          Engine
          <select value={backend.name} onChange={(event) => setBackendName(event.target.value)}>
            {backends.map((item) => (
              <option key={item.name} value={item.name}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Voice
          <input
            value={voice}
            onChange={(event) => setVoice(event.target.value)}
            list="voice-options"
            required
            placeholder="Type or select a voice"
          />
          <datalist id="voice-options">
            {voices.map((item) => (
              <option key={item} value={item} />
            ))}
          </datalist>
        </label>
        <label>
          Model
          <input value={model} onChange={(event) => setModel(event.target.value)} required />
        </label>
        <label>
          Speed <span className="value-label">{speed.toFixed(2)}×</span>
          <input
            type="range"
            min="0.5"
            max="2"
            step="0.05"
            value={speed}
            onChange={(event) => setSpeed(Number(event.target.value))}
          />
        </label>
        <label className="field-span">
          Chunk mode
          <select
            aria-label="Chunk mode"
            value={mode}
            onChange={(event) => setMode(event.target.value as ChunkingMode)}
          >
            {modes.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
          <small className="mode-detail">{modeDetail(mode)}</small>
        </label>
        <label>
          Character limit
          <input
            aria-label="Character limit"
            type="number"
            min="1"
            max={backend.max_characters}
            value={characterLimit}
            onChange={(event) => setCharacterLimit(Number(event.target.value))}
            required
          />
          <small>Backend maximum: {backend.max_characters.toLocaleString()}</small>
        </label>
      </div>
      <button className="primary-button" type="submit" disabled={disabled}>
        <span aria-hidden="true">▶</span> Generate audiobook
      </button>
    </form>
  );
}
