import { useEffect, useState } from 'react';

import { listBackendVoices } from '../api/client';
import type { Backend } from '../types';
import { VoiceSelector } from './VoiceSelector';

interface SettingsModalProps {
  backends: Backend[];
  voicePreferences: Record<string, string>;
  onSave: (preferences: Record<string, string>) => void;
  onClose: () => void;
}

export function SettingsModal({ backends, voicePreferences, onSave, onClose }: SettingsModalProps) {
  const [draft, setDraft] = useState<Record<string, string>>(voicePreferences);
  const [voices, setVoices] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const results: Record<string, string[]> = {};
      await Promise.all(
        backends.map(async (backend) => {
          try {
            const response = await listBackendVoices(backend.name);
            results[backend.name] = Array.from(new Set([backend.voice, ...response.voices]));
          } catch {
            // If the backend voices endpoint fails (e.g. engine not ready), still
            // allow the user to type a custom voice by seeding the datalist with
            // the backend's default voice and any saved preference.
            results[backend.name] = Array.from(
              new Set([backend.voice, voicePreferences[backend.name]].filter(Boolean)),
            );
          }
        }),
      );
      if (!cancelled) {
        setVoices(results);
        setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [backends, voicePreferences]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal settings-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>Settings</h2>
            <p className="modal-subtitle">Choose default voices for each TTS engine. Type any custom voice name.</p>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {loading ? (
          <p className="empty-state">Loading voices…</p>
        ) : (
          <div className="settings-list">
            {backends.map((backend) => (
              <label key={backend.name} className="settings-row">
                <span className="settings-engine">
                  <strong>{backend.name}</strong>
                  <small>{backend.model}</small>
                </span>
                <VoiceSelector
                  value={draft[backend.name] ?? backend.voice}
                  options={voices[backend.name] ?? []}
                  onChange={(selected) =>
                    setDraft((current) => ({
                      ...current,
                      [backend.name]: selected,
                    }))
                  }
                  placeholder="Enter custom voice name"
                />
              </label>
            ))}
          </div>
        )}

        <div className="settings-actions">
          <button className="secondary-button" onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary-button"
            onClick={() => {
              onSave(draft);
              onClose();
            }}
          >
            Save preferences
          </button>
        </div>
      </div>
    </div>
  );
}
