import '@testing-library/jest-dom';

import { fireEvent, render, screen } from '@testing-library/react';

import { GenerationForm } from '../components/GenerationForm';
import type { Backend } from '../types';

const backends: Backend[] = [
  {
    name: 'kokoro',
    base_url: 'http://kokoro:8880/v1',
    model: 'kokoro',
    voice: 'af_bella',
    max_characters: 4000,
  },
];

test('submits selected generation settings', async () => {
  const onSubmit = jest.fn();
  render(
    <GenerationForm backends={backends} disabled={false} onSubmit={onSubmit} text="Hello world." />,
  );

  await screen.findByRole('combobox', { name: 'Voice' });

  fireEvent.change(screen.getByLabelText('Chunk mode'), { target: { value: 'character' } });
  fireEvent.change(screen.getByLabelText('Character limit'), { target: { value: '800' } });
  fireEvent.click(screen.getByRole('button', { name: 'Generate audiobook' }));

  expect(onSubmit).toHaveBeenCalledWith({
    backend: 'kokoro',
    model: 'kokoro',
    voice: 'af_bella',
    speed: 1,
    chunking_mode: 'character',
    character_limit: 800,
  });
});
