import { useMemo, useState } from 'react';

const CUSTOM = '__custom__';

interface VoiceSelectorProps {
  value: string;
  options: string[];
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  id?: string;
}

export function VoiceSelector({
  value,
  options,
  onChange,
  placeholder = 'Custom voice name',
  required,
  id,
}: VoiceSelectorProps) {
  const normalizedOptions = useMemo(
    () => Array.from(new Set(options.filter(Boolean))),
    [options],
  );
  const isCustom = !normalizedOptions.includes(value);
  const [customValue, setCustomValue] = useState(isCustom ? value : '');

  return (
    <div className="voice-selector" id={id}>
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
