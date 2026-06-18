const WS_BASE = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000'

// Direct connection to Django/Daphne — token passed as URL query param
// because browser WebSocket API cannot send Authorization headers.
export function createEngineSocket(token, handlers) {
  const url = `${WS_BASE}/ws/engine/?token=${token}`
  const ws = new WebSocket(url)
  ws.onopen    = handlers.onOpen  ?? (() => {})
  ws.onmessage = (e) => handlers.onMessage?.(JSON.parse(e.data))
  ws.onclose   = handlers.onClose ?? (() => {})
  ws.onerror   = handlers.onError ?? (() => {})
  return ws
}
