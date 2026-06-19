import { CheckCircle2, Loader2, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { isApiError } from '@/api/client'
import {
  useDeleteExternalCredential,
  useExternalCredentials,
  useUpsertExternalCredential,
} from '@/hooks/useExternalCredentials'

const inputClass =
  'w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/30'

const submitClass =
  'rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-50'

export function ExternalModelSettings() {
  const { data: creds } = useExternalCredentials()
  const upsert = useUpsertExternalCredential()
  const remove = useDeleteExternalCredential()

  const [apiKey, setApiKey] = useState('')
  const [message, setMessage] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)

  const openai = creds?.find((c) => c.provider === 'openai')

  const save = async () => {
    setMessage(null)
    try {
      await upsert.mutateAsync({ provider: 'openai', auth_type: 'api_key', secret: apiKey.trim() })
      setApiKey('')
      setMessage({ kind: 'ok', text: 'OpenAI API key saved.' })
    } catch (err) {
      if (isApiError(err) && err.status === 503) {
        setMessage({
          kind: 'err',
          text: 'This server has not enabled external credentials (missing CREDENTIAL_ENCRYPTION_KEY).',
        })
      } else {
        setMessage({ kind: 'err', text: 'Could not save the API key.' })
      }
    }
  }

  const handleRemove = async () => {
    setMessage(null)
    try {
      await remove.mutateAsync('openai')
      setMessage({ kind: 'ok', text: 'API key removed.' })
    } catch {
      setMessage({ kind: 'err', text: 'Could not remove the API key.' })
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        When the local model repeatedly fails, the assistant can fall back to OpenAI (gpt-5.5)
        using your own API key. The key is stored encrypted and only its last digits are ever
        shown.
      </p>

      {openai && (
        <div className="flex items-center justify-between rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
          <span>
            Current key: <span className="font-mono">{openai.masked_hint}</span>
            <span
              className={`ml-2 rounded-full px-2 py-0.5 text-xs ${openai.status === 'active' ? 'bg-emerald-500/10 text-emerald-600' : 'bg-destructive/10 text-destructive'}`}
            >
              {openai.status}
            </span>
          </span>
          <button
            type="button"
            onClick={() => void handleRemove()}
            disabled={remove.isPending}
            className="flex items-center gap-1 text-xs text-destructive hover:underline disabled:opacity-50"
          >
            <Trash2 className="size-3.5" aria-hidden="true" />
            Remove
          </button>
        </div>
      )}

      <div>
        <label htmlFor="openai-api-key" className="mb-1 block text-sm font-medium">
          OpenAI API key
        </label>
        <input
          id="openai-api-key"
          type="password"
          autoComplete="off"
          placeholder="sk-…"
          className={inputClass}
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
      </div>

      {message && (
        <p
          role={message.kind === 'err' ? 'alert' : 'status'}
          className={`flex items-center gap-1.5 text-sm ${message.kind === 'ok' ? 'text-emerald-600' : 'text-destructive'}`}
        >
          {message.kind === 'ok' && <CheckCircle2 className="size-4" aria-hidden="true" />}
          {message.text}
        </p>
      )}

      <button
        type="button"
        onClick={() => void save()}
        disabled={!apiKey.trim() || upsert.isPending}
        className={`flex items-center gap-1.5 ${submitClass}`}
      >
        {upsert.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
        {openai ? 'Replace key' : 'Save key'}
      </button>
    </div>
  )
}
