export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {
    method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-Rematch-Intent': 'browser' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  })
  let data
  try { data = await response.json() } catch { throw new Error('The API server is unavailable. Check the backend and API proxy configuration.') }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the entered information and try again.')
  return data as T
}
