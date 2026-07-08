import { useState, useRef, useEffect, useCallback } from 'react';
import { previewVoice } from '../api/client';

export function useVoicePreview() {
  const [previewState, setPreviewState] = useState<'idle' | 'loading' | 'playing'>('idle');
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    setPreviewState('idle');
  }, []);

  const play = useCallback(
    async (
      backendName: string,
      params: { voice: string; model: string; speed?: number; text?: string },
    ) => {
      stop();
      setPreviewState('loading');
      setError(null);

      try {
        const blob = await previewVoice(backendName, params);
        const url = URL.createObjectURL(blob);
        objectUrlRef.current = url;

        const audio = new Audio(url);
        audioRef.current = audio;

        audio.addEventListener('ended', () => {
          stop();
        });

        audio.addEventListener('error', () => {
          setError('Audio playback failed');
          stop();
        });

        setPreviewState('playing');
        await audio.play();
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message || 'Failed to generate voice preview');
        setPreviewState('idle');
      }
    },
    [stop],
  );

  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
      }
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
      }
    };
  }, []);

  return { previewState, error, play, stop };
}
