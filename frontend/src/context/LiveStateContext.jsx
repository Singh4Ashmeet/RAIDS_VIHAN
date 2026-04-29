import { createContext, useContext } from 'react'

import useDispatchStore from '../store/dispatchStore'

const LiveStateContext = createContext(null)

export function LiveStateProvider({ children }) {
  const state = useDispatchStore()
  return (
    <LiveStateContext.Provider value={state}>
      {children}
    </LiveStateContext.Provider>
  )
}

export function useLiveState() {
  return useContext(LiveStateContext) || useDispatchStore()
}
