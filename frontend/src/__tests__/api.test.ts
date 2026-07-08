import { ApiError, createTextDocument, listBackends, previewVoice } from '../api/client';

beforeEach(() => {
  globalThis.fetch = jest.fn();
});

function mockResponse(body: unknown, status: number): Response {
  const text = typeof body === 'string' ? body : JSON.stringify(body);
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => text,
    json: async () => body,
  } as Response;
}

test('creates direct-text document through versioned API', async () => {
  const response = { id: 'document-1', title: 'Book', text: 'Text', revision: 1 };
  jest.mocked(globalThis.fetch).mockResolvedValue(mockResponse(response, 201));

  await expect(createTextDocument('Book', 'Text')).resolves.toMatchObject(response);
  expect(globalThis.fetch).toHaveBeenCalledWith(
    '/api/v1/documents',
    expect.objectContaining({ method: 'POST' }),
  );
});

test('surfaces backend problem detail', async () => {
  jest
    .mocked(globalThis.fetch)
    .mockResolvedValue(mockResponse({ detail: 'backend unavailable' }, 503));

  await expect(listBackends()).rejects.toEqual(new ApiError('backend unavailable', 503));
});

test('requests voice preview through versioned API', async () => {
  const mockBlob = new Blob(['audio_data'], { type: 'audio/mpeg' });
  jest.mocked(globalThis.fetch).mockResolvedValue({
    ok: true,
    status: 200,
    blob: async () => mockBlob,
  } as Response);

  await expect(
    previewVoice('kokoro', { voice: 'af_bella', model: 'kokoro', speed: 1.0, text: 'Hello' }),
  ).resolves.toBe(mockBlob);

  expect(globalThis.fetch).toHaveBeenCalledWith(
    '/api/v1/backends/kokoro/preview',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ voice: 'af_bella', model: 'kokoro', speed: 1.0, text: 'Hello' }),
    }),
  );
});
