export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {
    method, credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-Rematch-Intent': 'browser',
      'ngrok-skip-browser-warning': '1',
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  })
  const text = await response.text()
  let data
  try { data = JSON.parse(text) } catch {
    const hint = /ngrok/i.test(text)
      ? 'ngrok returned a warning or tunnel error. Check that the tunnel is online and points to port 8000.'
      : response.status >= 500
        ? 'The backend or proxy failed. Check the Python terminal on the Mac and the Vercel rewrite destination.'
        : 'Expected API JSON but received a page or plain text. Check the Vercel /api rewrite.'
    throw new Error(`API ${method} ${path}: HTTP ${response.status}. ${hint}`)
  }
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : `API ${method} ${path}: HTTP ${response.status}. Check the entered information and try again.`)
  return data as T
}
