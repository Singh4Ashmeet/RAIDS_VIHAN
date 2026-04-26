import { createContext, useContext, useEffect, useRef, useState } from 'react'

const defaultLiveState = {
  ambulances: [],
  hospitals: [],
  latestDispatch: null,
  dispatchHistory: [],
  notifications: [],
  isConnected: false,
  setLatestDispatch: () => {},
}

const LiveStateContext = createContext(defaultLiveState)

export function LiveStateProvider({ children }) {
  const [ambulances, setAmbulances] = useState([])
  const [hospitals, setHospitals] = useState([])
  const [latestDispatch, setLatestDispatchState] = useState(null)
  const [dispatchHistory, setDispatchHistory] = useState([])
  const [notifications, setNotifications] = useState([])
  const [isConnected, setIsConnected] = useState(false)
  const socketRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const unmountedRef = useRef(false)
  const initialConnectionRef = useRef(false)

  const setLatestDispatch = (dispatchPlan) => {
    setLatestDispatchState(dispatchPlan ?? null)
  }

  const handleMessage = (event) => {
    let message

    try {
      message = JSON.parse(event.data)
    } catch {
      return
    }

    switch (message?.type) {
      case 'state_snapshot':
        setAmbulances(message.ambulances ?? [])
        setHospitals(message.hospitals ?? [])
        break
      case 'simulation_tick':
        setAmbulances(message.ambulances ?? [])
        setHospitals((currentHospitals) => message.hospitals ?? currentHospitals)
        break
      case 'dispatch_created':
        if (!message.dispatch_plan) {
          return
        }
        setLatestDispatchState(message.dispatch_plan)
        setDispatchHistory((currentHistory) => [message.dispatch_plan, ...currentHistory])
        break
      case 'hospital_notification':
        setNotifications((currentNotifications) => [message, ...currentNotifications])
        break
      default:
        break
    }
  }

  function connect() {
    if (unmountedRef.current || socketRef.current) {
      return socketRef.current
    }

    const socket = new WebSocket('/ws/live')
    socketRef.current = socket

    socket.onopen = () => {
      setIsConnected(true)
    }

    socket.onmessage = handleMessage
    socket.onerror = () => {}
    socket.onclose = () => {
      if (socketRef.current === socket) {
        socketRef.current = null
      }
      setIsConnected(false)

      if (unmountedRef.current) {
        return
      }

      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = setTimeout(() => {
        connect()
      }, 3000)
    }

    return socket
  }

  if (!initialConnectionRef.current) {
    initialConnectionRef.current = true
    connect()
  }

  useEffect(() => {
    unmountedRef.current = false

    return () => {
      unmountedRef.current = true
      clearTimeout(reconnectTimerRef.current)

      const socket = socketRef.current
      socketRef.current = null

      if (socket && typeof socket.close === 'function') {
        socket.close()
      }

      if (globalThis.WebSocket?.instance === socket) {
        globalThis.WebSocket.instance = null
      }
    }
  }, [])

  return (
    <LiveStateContext.Provider
      value={{
        ambulances,
        hospitals,
        latestDispatch,
        dispatchHistory,
        notifications,
        isConnected,
        setLatestDispatch,
      }}
    >
      {children}
    </LiveStateContext.Provider>
  )
}

export function useLiveState() {
  return useContext(LiveStateContext) || defaultLiveState
}
