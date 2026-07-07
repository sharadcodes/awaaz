import '@testing-library/jest-dom';

import { fireEvent, render, screen } from '@testing-library/react';

import { JobCard } from '../components/JobCard';
import type { Job } from '../types';

const job: Job = {
  id: 'job-12345678',
  document_id: 'document-1',
  document_revision: 1,
  status: 'running',
  backend: 'kokoro',
  model: 'kokoro',
  voice: 'af_bella',
  speed: 1,
  chunking_mode: 'paragraph',
  character_limit: 1000,
  error: null,
  output_available: false,
  progress: { total: 10, completed: 4, failed: 0, processed: 4, percent: 40 },
  created_at: '2026-06-27T12:00:00Z',
  updated_at: '2026-06-27T12:01:00Z',
};

test('shows exact progress and exposes pause action', () => {
  const onAction = jest.fn();
  render(<JobCard job={job} onAction={onAction} />);

  expect(screen.getByText('4 / 10 chunks')).toBeInTheDocument();
  expect(screen.getByText('40%')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Pause' }));

  expect(onAction).toHaveBeenCalledWith('job-12345678', 'pause');
});
