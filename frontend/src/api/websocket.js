// Direct connection to Django/Daphne — token passed as URL query param
// because browser WebSocket API cannot send Authorization headers.
export function createEngineSocket(token, handlers) {
  const url = `ws://localhost:8000/ws/engine/?token=${token}`
  const ws = new WebSocket(url)
  ws.onopen    = handlers.onOpen  ?? (() => {})
  ws.onmessage = (e) => handlers.onMessage?.(JSON.parse(e.data))
  ws.onclose   = handlers.onClose ?? (() => {})
  ws.onerror   = handlers.onError ?? (() => {})
  return ws
}
