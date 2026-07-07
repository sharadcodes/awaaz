import { useState } from 'react';

interface NewDocumentProps {
  busy: boolean;
  onCreate: (title: string, text: string) => void;
  onUpload: (file: File, title?: string) => void;
}

export function NewDocument({ busy, onCreate, onUpload }: NewDocumentProps) {
  const [mode, setMode] = useState<'upload' | 'text'>('upload');
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);

  return (
    <section className="new-document">
      <div className="segmented-control" aria-label="Input method">
        <button className={mode === 'upload' ? 'active' : ''} onClick={() => setMode('upload')}>
          Upload file
        </button>
        <button className={mode === 'text' ? 'active' : ''} onClick={() => setMode('text')}>
          Paste text
        </button>
      </div>

      {mode === 'upload' ? (
        <form
          className="new-document-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (file) onUpload(file, title || undefined);
          }}
        >
          <label className="drop-zone">
            <input
              type="file"
              accept=".epub,.txt,text/plain,application/epub+zip"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              required
            />
            <span className="upload-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 16V4m0 0L8 8m4-4l4 4M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2"
                />
              </svg>
            </span>
            <strong>{file ? file.name : 'Choose EPUB or TXT'}</strong>
            <small>{file ? `${(file.size / 1024).toFixed(1)} KB` : 'Maximum 100 MB'}</small>
          </label>
          <label className="field-label">
            <span className="field-label-text">
              Title override <span className="optional">optional</span>
            </span>
            <input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <button className="primary-button" disabled={busy || !file} type="submit">
            {busy ? 'Importing…' : 'Import manuscript'}
          </button>
        </form>
      ) : (
        <form
          className="new-document-form"
          onSubmit={(event) => {
            event.preventDefault();
            onCreate(title, text);
          }}
        >
          <label className="field-label">
            <span className="field-label-text">Book title</span>
            <input value={title} onChange={(event) => setTitle(event.target.value)} required />
          </label>
          <label className="field-label">
            <span className="field-label-text">Manuscript text</span>
            <textarea
              className="paste-area"
              value={text}
              onChange={(event) => setText(event.target.value)}
              required
            />
          </label>
          <button className="primary-button" disabled={busy} type="submit">
            {busy ? 'Adding…' : 'Add manuscript'}
          </button>
        </form>
      )}
    </section>
  );
}
