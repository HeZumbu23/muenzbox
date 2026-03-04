import { adminGetChildren, endSession, getChildren, verifyPin } from './api'

describe('api request helpers', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads children from public endpoint', async () => {
    const payload = [{ id: 1, name: 'Mia' }]
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(payload),
    })

    const result = await getChildren()

    expect(result).toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith('/api/children', expect.objectContaining({
      headers: expect.objectContaining({
        'Content-Type': 'application/json',
      }),
    }))
  })

  it('sends auth token for admin endpoints', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue([]),
    })

    await adminGetChildren('token-123')

    expect(fetchMock).toHaveBeenCalledWith('/api/admin/children', expect.objectContaining({
      headers: expect.objectContaining({
        Authorization: 'Bearer token-123',
      }),
    }))
  })

  it('returns null for 204 responses', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 204,
      json: vi.fn(),
    })

    await expect(endSession(22, 't')).resolves.toBeNull()
  })

  it('throws parsed API error details for failed requests', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
      json: vi.fn().mockResolvedValue({ detail: 'Falsche PIN!' }),
    })

    await expect(verifyPin(2, '1111')).rejects.toMatchObject({
      message: 'Falsche PIN!',
      status: 401,
    })
  })
})
