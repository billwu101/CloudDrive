import { zodResolver } from '@hookform/resolvers/zod'
import { Cloud } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { isApiError } from '@/api/client'
import { useRegisterMutation } from '@/hooks/useAuth'

const schema = z
  .object({
    email: z.string().email('Invalid email address'),
    username: z.string().min(2, 'Username must be at least 2 characters'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirmPassword: z.string().min(1, 'Please confirm your password'),
  })
  .refine((d) => d.password === d.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })

type FormValues = z.infer<typeof schema>

export function RegisterPage() {
  const navigate = useNavigate()
  const registerMutation = useRegisterMutation()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: FormValues) => {
    try {
      await registerMutation.mutateAsync({
        email: values.email,
        username: values.username,
        password: values.password,
      })
      navigate('/drive')
    } catch (err) {
      const message = isApiError(err) ? err.message : 'Registration failed. Please try again.'
      setError('root', { message })
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex items-center gap-2">
          <div className="flex size-9 items-center justify-center rounded-lg bg-primary">
            <Cloud className="size-5 text-primary-foreground" aria-hidden="true" />
          </div>
          <span className="text-xl font-semibold">Cloud Drive</span>
        </div>

        <h1 className="text-2xl font-semibold text-foreground">Create an account</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Already have an account?{' '}
          <Link to="/login" className="text-primary underline-offset-4 hover:underline">
            Sign in
          </Link>
        </p>

        <form onSubmit={handleSubmit(onSubmit)} noValidate className="mt-6 space-y-4">
          {errors.root && (
            <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {errors.root.message}
            </p>
          )}

          {(
            [
              { id: 'email', label: 'Email', type: 'email', autoComplete: 'email' },
              { id: 'username', label: 'Username', type: 'text', autoComplete: 'username' },
              { id: 'password', label: 'Password', type: 'password', autoComplete: 'new-password' },
              { id: 'confirmPassword', label: 'Confirm password', type: 'password', autoComplete: 'new-password' },
            ] as const
          ).map(({ id, label, type, autoComplete }) => (
            <div key={id}>
              <label htmlFor={id} className="mb-1 block text-sm font-medium">
                {label}
              </label>
              <input
                id={id}
                type={type}
                autoComplete={autoComplete}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/30 aria-[invalid=true]:border-destructive"
                aria-invalid={!!errors[id]}
                {...register(id)}
              />
              {errors[id] && (
                <p className="mt-1 text-xs text-destructive">{errors[id]?.message}</p>
              )}
            </div>
          ))}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>
      </div>
    </main>
  )
}
