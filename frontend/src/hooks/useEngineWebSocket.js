import { useRef, useState, useCallback } from 'react'
import { createEngineSocket } from '../api/websocket.js'
import { generateSample } from '../lib/sensorGenerator.js'

export function useEngineWebSocket({ engineModel, engineType, onMessage, onSample }) {
  const wsRef       = useRef(null)
  const intervalRef = useRef(null)
  // Mutable refs so interval closure always reads the latest values
  const leakModeRef  = useRef('healthy')
  const leakTypeRef  = useRef('charge_air')
  const onMessageRef = useRef(onMessage)
  const onSampleRef  = useRef(onSample)
  const [isConnected, setIsConnected] = useState(false)

  // Keep refs in sync with latest prop values
  onMessageRef.current = onMessage
  onSampleRef.current  = onSample

  const setLeakConfig = useCallback((mode, type) => {
    leakModeRef.current = mode
    leakTypeRef.current = type
  }, [])

  const connect = useCallback(() => {
    const token = sessionStorage.getItem('cat_token')
    if (!token) return

    wsRef.current = createEngineSocket(token, {
      onOpen: () => {
        wsRef.current.send(JSON.stringify({
          model_no:    engineModel || 'CAT-3412-001',
          engine_type: engineType  || 'diesel',
        }))
      },
      onMessage: (msg) => {
        if (msg.type === 'engine_registered') {
          setIsConnected(true)
          intervalRef.current = setInterval(() => {
            if (wsRef.current?.readyState !== WebSocket.OPEN) return
            const sample = generateSample(leakModeRef.current, leakTypeRef.current)
            wsRef.current.send(JSON.stringify(sample))
            onSampleRef.current?.(sample)
          }, 500)
        }
        onMessageRef.current?.(msg)
      },
      onClose: () => {
        setIsConnected(false)
        clearInterval(intervalRef.current)
        intervalRef.current = null
      },
      onError: () => {
        setIsConnected(false)
        clearInterval(intervalRef.current)
        intervalRef.current = null
      },
    })
  }, [engineModel, engineType])

  const disconnect = useCallback(() => {
    clearInterval(intervalRef.current)
    intervalRef.current = null
    wsRef.current?.close()
    wsRef.current = null
    setIsConnected(false)
  }, [])

  return { connect, disconnect, isConnected, setLeakConfig }
}
