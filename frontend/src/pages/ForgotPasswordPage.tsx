import { zodResolver } from '@hookform/resolvers/zod'
import { Cloud } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'

import { isApiError } from '@/api/client'
import { useForgotPasswordMutation } from '@/hooks/useAuth'

const schema = z.object({
  email: z.string().email('Invalid email address'),
})

type FormValues = z.infer<typeof schema>

export function ForgotPasswordPage() {
  const forgotPasswordMutation = useForgotPasswordMutation()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting, isSubmitSuccessful },
    setError,
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const onSubmit = async (values: FormValues) => {
    try {
      await forgotPasswordMutation.mutateAsync(values.email)
    } catch (err) {
      const message = isApiError(err)
        ? err.message
        : 'Something went wrong. Please try again.'
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

        <h1 className="text-2xl font-semibold text-foreground">Reset your password</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Enter your account email and we'll send you a temporary password.
        </p>

        {isSubmitSuccessful && !errors.root ? (
          <div
            role="status"
            className="mt-6 rounded-md bg-primary/10 px-4 py-3 text-sm text-foreground"
          >
            If an account exists for that email, a temporary password has been sent.
            Check your inbox, sign in, then change your password right away.
            <div className="mt-4">
              <Link
                to="/login"
                className="text-primary underline-offset-4 hover:underline"
              >
                Back to sign in
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} noValidate className="mt-6 space-y-4">
            {errors.root && (
              <p
                role="alert"
                className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {errors.root.message}
              </p>
            )}

            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-medium">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/30 aria-[invalid=true]:border-destructive"
                aria-invalid={!!errors.email}
                {...register('email')}
              />
              {errors.email && (
                <p className="mt-1 text-xs text-destructive">{errors.email.message}</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {isSubmitting ? 'Sending…' : 'Send reset password'}
            </button>

            <p className="text-center text-sm text-muted-foreground">
              <Link to="/login" className="text-primary underline-offset-4 hover:underline">
                Back to sign in
              </Link>
            </p>
          </form>
        )}
      </div>
    </main>
  )
}
