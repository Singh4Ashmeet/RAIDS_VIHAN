import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Lock, User } from 'lucide-react'

import useAuthStore from '../store/authStore'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useAuthStore((state) => state.login)
  const isLoading = useAuthStore((s) => s.isLoading)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const role = useAuthStore((s) => s.role)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!error) return undefined
    const t = setTimeout(() => setError(null), 5000)
    return () => clearTimeout(t)
  }, [error])

  useEffect(() => {
    if (!isAuthenticated) return
    navigate(role === 'admin' ? '/admin/command' : '/user/sos', { replace: true })
  }, [isAuthenticated, role, navigate])

  async function handleSignIn() {
    setError(null)
    const result = await login(username.trim(), password)
    if (result.ok) {
      if (result.role === 'admin') navigate('/admin/command')
      else navigate('/user/sos')
    } else {
      setError(result.message || 'Invalid credentials')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface p-3 sm:p-4">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-5 sm:p-8">
        <div className="mb-8">
          <div className="mb-2 flex items-center gap-3">
            <span className="relative inline-flex h-3 w-3">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-500 opacity-75"/>
              <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500"/>
            </span>
            <span className="text-[20px] font-bold text-white">RAID Nexus</span>
          </div>
          <h1 className="mb-1 text-2xl font-semibold text-white">
            Welcome back
          </h1>
          <p className="text-sm text-slate-400">Sign in to continue</p>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <Input
            label="Username"
            icon={User}
            type="text"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <Input
            label="Password"
            icon={Lock}
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            rightElement={(
              <button
                type="button"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                title={showPassword ? 'Hide password' : 'Show password'}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-100 focus:outline-none focus:ring-2 focus:ring-brand-500"
                onClick={() => setShowPassword((visible) => !visible)}
              >
                {showPassword ? <EyeOff size={16}/> : <Eye size={16}/>}
              </button>
            )}
          />
          <Button
            variant="primary"
            size="lg"
            className="w-full"
            loading={isLoading}
            onClick={handleSignIn}
          >
            Sign in
          </Button>
        </div>

        <p className="mt-4 text-center text-sm text-slate-400">
          Don&apos;t have an account?{' '}
          <Link to="/login" className="text-brand-400 hover:underline">
            Get started
          </Link>
        </p>

        <div className="mt-6 border-t border-border pt-6">
          <p className="mb-3 text-xs uppercase tracking-wider text-slate-500">
            Demo credentials
          </p>
          <div className="space-y-1.5">
            <p className="font-mono text-xs text-slate-300">
              Admin username: admin
            </p>
            <p className="font-mono text-xs text-slate-300">
              User username: user
            </p>
            <p className="text-xs text-slate-500">
              Use the deployment password configured by the administrator.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
