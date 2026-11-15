export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {
    method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-Rematch-Intent': 'browser' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  })
  let data
  try { data = await response.json() } catch { throw new Error('The local server is unavailable. Try again in a moment.') }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the entered information and try again.')
  return data as T
}
