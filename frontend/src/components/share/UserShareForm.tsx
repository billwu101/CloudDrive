import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { isApiError } from '@/api/client'
import { type Permission, useShareWithUser } from '@/hooks/useShare'

import { PermissionSelect } from './PermissionSelect'

const schema = z.object({
  email: z.string().email('Invalid email address'),
})

type FormValues = z.infer<typeof schema>

interface UserShareFormProps {
  itemId: string
}

export function UserShareForm({ itemId }: UserShareFormProps) {
  const [permission, setPermission] = useState<Permission>('viewer')
  const shareWithUser = useShareWithUser()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
    setError,
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const onSubmit = async ({ email }: FormValues) => {
    try {
      await shareWithUser.mutateAsync({ itemId, targetEmail: email, permission })
      reset()
    } catch (err) {
      const msg = isApiError(err) ? err.message : 'Failed to share'
      setError('root', { message: msg })
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-2">
      <div className="flex gap-2">
        <div className="min-w-0 flex-1">
          <input
            type="email"
            placeholder="Email address"
            aria-label="Email to share with"
            aria-invalid={!!errors.email}
            className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/30 aria-[invalid=true]:border-destructive"
            {...register('email')}
          />
        </div>
        <PermissionSelect value={permission} onChange={setPermission} />
        <button
          type="submit"
          disabled={shareWithUser.isPending}
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-50"
        >
          Share
        </button>
      </div>
      {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
      {errors.root && <p className="text-xs text-destructive">{errors.root.message}</p>}
      {shareWithUser.isSuccess && (
        <p className="text-xs text-green-600">Shared successfully!</p>
      )}
    </form>
  )
}
