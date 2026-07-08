import { useMemo, useState } from 'react';

const CUSTOM = '__custom__';

interface VoiceSelectorProps {
  value: string;
  options: string[];
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
  onPreview?: () => void;
  previewState?: 'idle' | 'loading' | 'playing';
}

export function VoiceSelector({
  value,
  options,
  onChange,
  placeholder = 'Custom voice name',
  required,
  id,
  onPreview,
  previewState = 'idle',
}: VoiceSelectorProps) {
  const normalizedOptions = useMemo(() => Array.from(new Set(options.filter(Boolean))), [options]);
  const isCustom = !normalizedOptions.includes(value);
  const [customValue, setCustomValue] = useState(isCustom ? value : '');

  return (
    <div className="voice-selector" id={id}>
      <div className="voice-selector-row">
        <select
          value={isCustom ? CUSTOM : value}
          onChange={(event) => {
            const selected = event.target.value;
            if (selected === CUSTOM) {
              onChange(customValue || '');
            } else {
              onChange(selected);
            }
          }}
        >
          {normalizedOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
          <option value={CUSTOM}>Custom…</option>
        </select>
        {onPreview && (
          <button
            type="button"
            className={`preview-button${previewState === 'playing' ? ' playing' : ''}`}
            onClick={onPreview}
            disabled={!value}
            title={previewState === 'playing' ? 'Stop preview' : 'Play preview'}
            aria-label={previewState === 'playing' ? 'Stop preview' : 'Play preview'}
          >
            {previewState === 'loading' ? (
              <svg
                className="spinner-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="3"
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="10" strokeDasharray="32 20" />
              </svg>
            ) : previewState === 'playing' ? (
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <rect x="6" y="6" width="12" height="12" rx="1.5" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </button>
        )}
      </div>
      {isCustom && (
        <input
          value={customValue}
          onChange={(event) => {
            setCustomValue(event.target.value);
            onChange(event.target.value);
          }}
          placeholder={placeholder}
          required={required}
        />
      )}
    </div>
  );
}
