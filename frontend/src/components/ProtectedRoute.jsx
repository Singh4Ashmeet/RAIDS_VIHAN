import { Navigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'

export function RequireAuth({ children, role }) {
  const { isAuthed, role: userRole } = useAuthStore()
  if (!isAuthed()) return <Navigate to="/login" replace/>
  if (role && userRole !== role && userRole !== 'admin')
    return <Navigate to="/user/sos" replace/>
  return children
}
