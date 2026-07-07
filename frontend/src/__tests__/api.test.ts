import { ApiError, createTextDocument, listBackends } from '../api/client';

beforeEach(() => {
  globalThis.fetch = jest.fn();
});

function mockResponse(body: unknown, status: number): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
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
