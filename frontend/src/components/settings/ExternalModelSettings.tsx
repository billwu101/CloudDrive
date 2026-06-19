import { CheckCircle2, Loader2, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { isApiError } from '@/api/client'
import {
  useDeleteExternalCredential,
  useExternalCredentials,
  useUpsertExternalCredential,
} from '@/hooks/useExternalCredentials'
import type { ExternalCredentialView } from '@/api/types'

const inputClass =
  'w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/30'

const submitClass =
  'rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-50'

type Message = { kind: 'ok' | 'err'; text: string } | null

function CredentialStatus({
  cred,
  label,
  onRemove,
  removing,
}: {
  cred: ExternalCredentialView
  label: string
  onRemove: () => void
  removing: boolean
}) {
  return (
    <div className="flex items-center justify-between rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
      <span>
        {label}: <span className="font-mono">{cred.masked_hint}</span>
        <span
          className={`ml-2 rounded-full px-2 py-0.5 text-xs ${cred.status === 'active' ? 'bg-emerald-500/10 text-emerald-600' : 'bg-destructive/10 text-destructive'}`}
        >
          {cred.status}
        </span>
      </span>
      <button
        type="button"
        onClick={onRemove}
        disabled={removing}
        className="flex items-center gap-1 text-xs text-destructive hover:underline disabled:opacity-50"
      >
        <Trash2 className="size-3.5" aria-hidden="true" />
        Remove
      </button>
    </div>
  )
}

export function ExternalModelSettings() {
  const { data: creds } = useExternalCredentials()
  const upsert = useUpsertExternalCredential()
  const remove = useDeleteExternalCredential()

  const [apiKey, setApiKey] = useState('')
  const [codexAuth, setCodexAuth] = useState('')
  const [message, setMessage] = useState<Message>(null)

  const openai = creds?.find((c) => c.provider === 'openai')
  const codex = creds?.find((c) => c.provider === 'codex')

  const notEnabledText =
    'This server has not enabled external credentials (missing CREDENTIAL_ENCRYPTION_KEY).'

  const saveOpenai = async () => {
    setMessage(null)
    try {
      await upsert.mutateAsync({ provider: 'openai', auth_type: 'api_key', secret: apiKey.trim() })
      setApiKey('')
      setMessage({ kind: 'ok', text: 'OpenAI API key saved.' })
    } catch (err) {
      const text = isApiError(err) && err.status === 503 ? notEnabledText : 'Could not save the API key.'
      setMessage({ kind: 'err', text })
    }
  }

  const saveCodex = async () => {
    setMessage(null)
    try {
      await upsert.mutateAsync({ provider: 'codex', auth_type: 'oauth_token', secret: codexAuth.trim() })
      setCodexAuth('')
      setMessage({ kind: 'ok', text: 'Codex subscription saved.' })
    } catch (err) {
      const text =
        isApiError(err) && err.status === 503 ? notEnabledText : 'Could not save the Codex credential.'
      setMessage({ kind: 'err', text })
    }
  }

  const removeProvider = async (provider: 'openai' | 'codex', noun: string) => {
    setMessage(null)
    try {
      await remove.mutateAsync(provider)
      setMessage({ kind: 'ok', text: `${noun} removed.` })
    } catch {
      setMessage({ kind: 'err', text: `Could not remove the ${noun.toLowerCase()}.` })
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        When the local model repeatedly fails, the assistant can fall back to GPT-5.5. A Codex
        subscription is tried first; if you also set an OpenAI API key it is used as a backup.
        Credentials are stored encrypted and only masked hints are ever shown.
      </p>

      {/* Codex subscription (tried first) */}
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">Codex subscription</h4>
        {codex && (
          <CredentialStatus
            cred={codex}
            label="Token"
            onRemove={() => void removeProvider('codex', 'Codex credential')}
            removing={remove.isPending}
          />
        )}
        {codex?.status === 'invalid' && (
          <p className="text-xs text-destructive">
            This subscription token was rejected. Re-run `codex login` and paste the new auth.json.
          </p>
        )}
        <label htmlFor="codex-auth" className="mb-1 block text-sm font-medium">
          auth.json from `codex login`
        </label>
        <textarea
          id="codex-auth"
          autoComplete="off"
          rows={3}
          placeholder='{"tokens":{"access_token":"…","refresh_token":"…"}}'
          className={`${inputClass} font-mono`}
          value={codexAuth}
          onChange={(e) => setCodexAuth(e.target.value)}
        />
        <button
          type="button"
          onClick={() => void saveCodex()}
          disabled={!codexAuth.trim() || upsert.isPending}
          className={`flex items-center gap-1.5 ${submitClass}`}
        >
          {upsert.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          {codex ? 'Replace subscription' : 'Save subscription'}
        </button>
      </div>

      <hr className="border-border" />

      {/* OpenAI API key (fallback) */}
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">OpenAI API key</h4>
        {openai && (
          <CredentialStatus
            cred={openai}
            label="Current key"
            onRemove={() => void removeProvider('openai', 'API key')}
            removing={remove.isPending}
          />
        )}
        {openai?.status === 'invalid' && (
          <p className="text-xs text-destructive">
            This key was rejected (invalid or out of quota). Replace it to keep using GPT-5.5 fallback.
          </p>
        )}
        <label htmlFor="openai-api-key" className="mb-1 block text-sm font-medium">
          API key
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
        <button
          type="button"
          onClick={() => void saveOpenai()}
          disabled={!apiKey.trim() || upsert.isPending}
          className={`flex items-center gap-1.5 ${submitClass}`}
        >
          {upsert.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          {openai ? 'Replace key' : 'Save key'}
        </button>
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
    </div>
  )
}
