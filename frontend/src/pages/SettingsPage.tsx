import { zodResolver } from '@hookform/resolvers/zod'
import {
  CheckCircle2,
  KeyRound,
  LoaderCircle,
  Mail,
  ShieldCheck,
  Sparkles,
  UserRound,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { isApiError } from '@/api/client'
import { ExternalModelSettings } from '@/components/settings/ExternalModelSettings'
import {
  useChangePasswordMutation,
  useCurrentUserQuery,
  useUpdateEmailMutation,
  useUpdateUsernameMutation,
} from '@/hooks/useAuth'

// ---------- schemas ----------

const usernameSchema = z.object({
  username: z.string().min(1, 'Username is required').max(255),
})

const emailSchema = z.object({
  email: z.string().email('Invalid email address').max(255),
})

const passwordSchema = z
  .object({
    currentPassword: z.string().min(1, 'Current password is required'),
    newPassword: z.string().min(8, 'New password must be at least 8 characters').max(128),
    confirmPassword: z.string().min(1, 'Please confirm your new password'),
  })
  .refine((d) => d.newPassword === d.confirmPassword, {
    message: 'Passwords do not match',
    path: ['confirmPassword'],
  })

type UsernameValues = z.infer<typeof usernameSchema>
type EmailValues = z.infer<typeof emailSchema>
type PasswordValues = z.infer<typeof passwordSchema>

// ---------- shared UI ----------

interface SectionCardProps {
  title: string
  description: string
  icon: ReactNode
  children: ReactNode
}

function SectionCard({ title, description, icon, children }: SectionCardProps) {
  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-sm sm:p-6">
      <div className="mb-5 flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted text-foreground">
          {icon}
        </div>
        <div>
          <h2 className="text-base font-semibold text-foreground">{title}</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="max-w-xl">{children}</div>
    </section>
  )
}

function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return <p className="mt-1 text-xs text-destructive">{message}</p>
}

function RootError({ message }: { message?: string }) {
  if (!message) return null
  return (
    <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
      {message}
    </p>
  )
}

function SuccessBadge({ message }: { message: string }) {
  return (
    <p role="status" className="flex items-center gap-1.5 text-sm text-emerald-600">
      <CheckCircle2 className="size-4" aria-hidden="true" />
      {message}
    </p>
  )
}

const inputClass =
  'w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/30 aria-[invalid=true]:border-destructive'

const submitClass =
  'rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

// ---------- sub-forms ----------

function UsernameForm({ currentUsername }: { currentUsername: string }) {
  const mutation = useUpdateUsernameMutation()
  const [success, setSuccess] = useState(false)

  const {
    register,
    handleSubmit,
    reset,
    clearErrors,
    formState: { errors, isDirty, isSubmitting },
    setError,
  } = useForm<UsernameValues>({
    resolver: zodResolver(usernameSchema),
    defaultValues: { username: currentUsername },
  })

  const onSubmit = async (values: UsernameValues) => {
    setSuccess(false)
    clearErrors('root')
    try {
      const updatedUser = await mutation.mutateAsync(values.username)
      reset({ username: updatedUser.username })
      setSuccess(true)
    } catch (err) {
      const message = isApiError(err) ? err.message : 'Failed to update username.'
      setError('root', { message })
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-3">
      <RootError message={errors.root?.message} />
      {success && <SuccessBadge message="Username updated." />}
      <div>
        <label htmlFor="username" className="mb-1 block text-sm font-medium">
          Username
        </label>
        <input
          id="username"
          type="text"
          autoComplete="username"
          className={inputClass}
          aria-invalid={!!errors.username}
          {...register('username')}
        />
        <FieldError message={errors.username?.message} />
      </div>
      <button type="submit" disabled={!isDirty || isSubmitting} className={submitClass}>
        {isSubmitting ? 'Saving…' : 'Save username'}
      </button>
    </form>
  )
}

function EmailForm({ currentEmail }: { currentEmail: string }) {
  const mutation = useUpdateEmailMutation()
  const [success, setSuccess] = useState(false)

  const {
    register,
    handleSubmit,
    reset,
    clearErrors,
    formState: { errors, isDirty, isSubmitting },
    setError,
  } = useForm<EmailValues>({
    resolver: zodResolver(emailSchema),
    defaultValues: { email: currentEmail },
  })

  const onSubmit = async (values: EmailValues) => {
    setSuccess(false)
    clearErrors('root')
    try {
      const updatedUser = await mutation.mutateAsync(values.email)
      reset({ email: updatedUser.email })
      setSuccess(true)
    } catch (err) {
      const message = isApiError(err) ? err.message : 'Failed to update email.'
      setError('root', { message })
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-3">
      <RootError message={errors.root?.message} />
      {success && <SuccessBadge message="Email updated." />}
      <div>
        <label htmlFor="email" className="mb-1 block text-sm font-medium">
          Email address
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          className={inputClass}
          aria-invalid={!!errors.email}
          {...register('email')}
        />
        <FieldError message={errors.email?.message} />
      </div>
      <button type="submit" disabled={!isDirty || isSubmitting} className={submitClass}>
        {isSubmitting ? 'Saving…' : 'Save email'}
      </button>
    </form>
  )
}

function PasswordForm() {
  const mutation = useChangePasswordMutation()
  const [success, setSuccess] = useState(false)

  const {
    register,
    handleSubmit,
    reset,
    clearErrors,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<PasswordValues>({ resolver: zodResolver(passwordSchema) })

  const onSubmit = async (values: PasswordValues) => {
    setSuccess(false)
    clearErrors('root')
    try {
      await mutation.mutateAsync({
        currentPassword: values.currentPassword,
        newPassword: values.newPassword,
      })
      setSuccess(true)
      reset()
    } catch (err) {
      const message = isApiError(err) ? err.message : 'Failed to change password.'
      setError('root', { message })
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-3">
      <RootError message={errors.root?.message} />
      {success && <SuccessBadge message="Password changed successfully." />}
      <div>
        <label htmlFor="currentPassword" className="mb-1 block text-sm font-medium">
          Current password
        </label>
        <input
          id="currentPassword"
          type="password"
          autoComplete="current-password"
          className={inputClass}
          aria-invalid={!!errors.currentPassword}
          {...register('currentPassword')}
        />
        <FieldError message={errors.currentPassword?.message} />
      </div>
      <div>
        <label htmlFor="newPassword" className="mb-1 block text-sm font-medium">
          New password
        </label>
        <input
          id="newPassword"
          type="password"
          autoComplete="new-password"
          className={inputClass}
          aria-invalid={!!errors.newPassword}
          {...register('newPassword')}
        />
        <FieldError message={errors.newPassword?.message} />
      </div>
      <div>
        <label htmlFor="confirmPassword" className="mb-1 block text-sm font-medium">
          Confirm new password
        </label>
        <input
          id="confirmPassword"
          type="password"
          autoComplete="new-password"
          className={inputClass}
          aria-invalid={!!errors.confirmPassword}
          {...register('confirmPassword')}
        />
        <FieldError message={errors.confirmPassword?.message} />
      </div>
      <button type="submit" disabled={isSubmitting} className={submitClass}>
        {isSubmitting ? 'Saving…' : 'Change password'}
      </button>
    </form>
  )
}

// ---------- page ----------

export function SettingsPage() {
  const { data: user, isPending, isError } = useCurrentUserQuery()

  if (isPending) {
    return (
      <div className="flex min-h-72 items-center justify-center text-muted-foreground">
        <LoaderCircle className="mr-2 size-5 animate-spin" aria-hidden="true" />
        Loading account settings…
      </div>
    )
  }

  if (isError || !user) {
    return (
      <div
        role="alert"
        className="mx-auto mt-8 max-w-2xl rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive"
      >
        Account settings could not be loaded. Please refresh the page and try again.
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl px-1 py-4 sm:px-4 sm:py-8">
      <header className="mb-7">
        <div className="mb-3 flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <ShieldCheck className="size-6" aria-hidden="true" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">
          Account Settings
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage your profile details and keep your account secure.
        </p>
      </header>
      <div className="space-y-6">
        <SectionCard
          title="Username"
          description="This name is shown throughout your cloud drive."
          icon={<UserRound className="size-5" aria-hidden="true" />}
        >
          <UsernameForm currentUsername={user.username} />
        </SectionCard>
        <SectionCard
          title="Email address"
          description="Use this email the next time you sign in."
          icon={<Mail className="size-5" aria-hidden="true" />}
        >
          <EmailForm currentEmail={user.email} />
        </SectionCard>
        <SectionCard
          title="Password"
          description="Choose a password with at least 8 characters."
          icon={<KeyRound className="size-5" aria-hidden="true" />}
        >
          <PasswordForm />
        </SectionCard>
        <SectionCard
          title="External AI model"
          description="Optional: let the assistant fall back to OpenAI when the local model can't deliver."
          icon={<Sparkles className="size-5" aria-hidden="true" />}
        >
          <ExternalModelSettings />
        </SectionCard>
      </div>
    </div>
  )
}
