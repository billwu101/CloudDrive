import { CheckCircle2, Loader2, Trash2 } from 'lucide-react'
import { useState } from 'react'

import { isApiError } from '@/api/client'
import {
  useCreateModelConnection,
  useDeleteModelConnection,
  useModelConnections,
} from '@/hooks/useExternalCredentials'
import type { ConnectionKind, ConnectionView } from '@/api/types'

const inputClass =
  'w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/30'

const submitClass =
  'rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80 disabled:opacity-50'

type Message = { kind: 'ok' | 'err'; text: string } | null

// Common endpoints to prefill base_url and reduce confusion. The user still
// names the connection themselves (so a Gemini key isn't labelled "OpenAI").
const PRESETS: Record<string, { kind: ConnectionKind; base_url: string; model: string }> = {
  Gemini: {
    kind: 'openai_compatible',
    base_url: 'https://generativelanguage.googleapis.com/v1beta/openai',
    model: 'gemini-2.5-flash-lite',
  },
  OpenAI: { kind: 'openai_compatible', base_url: 'https://api.openai.com/v1', model: 'gpt-5.5' },
  // Ollama cloud works best via its OpenAI-compatible endpoint (supports the
  // planner's structured output); the native "ollama" kind is for self-hosted.
  'Ollama cloud': {
    kind: 'openai_compatible',
    base_url: 'https://ollama.com/v1',
    model: 'gpt-oss:20b',
  },
  Codex: { kind: 'codex', base_url: '', model: '' },
}

function ConnectionRow({
  conn,
  onRemove,
  removing,
}: {
  conn: ConnectionView
  onRemove: () => void
  removing: boolean
}) {
  return (
    <div className="flex items-center justify-between rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
      <span className="min-w-0 truncate">
        <span className="font-medium">{conn.label}</span>
        <span className="ml-2 text-xs text-muted-foreground">
          {conn.kind}
          {conn.model ? ` · ${conn.model}` : ''} · <span className="font-mono">{conn.masked_hint}</span>
        </span>
        <span
          className={`ml-2 rounded-full px-2 py-0.5 text-xs ${conn.status === 'active' ? 'bg-emerald-500/10 text-emerald-600' : 'bg-destructive/10 text-destructive'}`}
        >
          {conn.status}
        </span>
      </span>
      <button
        type="button"
        onClick={onRemove}
        disabled={removing}
        className="flex shrink-0 items-center gap-1 text-xs text-destructive hover:underline disabled:opacity-50"
      >
        <Trash2 className="size-3.5" aria-hidden="true" />
        Remove
      </button>
    </div>
  )
}

export function ExternalModelSettings() {
  const { data: connections } = useModelConnections()
  const create = useCreateModelConnection()
  const remove = useDeleteModelConnection()

  const [label, setLabel] = useState('')
  const [kind, setKind] = useState<ConnectionKind>('openai_compatible')
  const [baseUrl, setBaseUrl] = useState(PRESETS.Gemini.base_url)
  const [model, setModel] = useState(PRESETS.Gemini.model)
  const [secret, setSecret] = useState('')
  const [message, setMessage] = useState<Message>(null)

  const applyPreset = (name: string) => {
    const preset = PRESETS[name]
    if (!preset) return
    setKind(preset.kind)
    setBaseUrl(preset.base_url)
    setModel(preset.model)
    if (!label) setLabel(name)
  }

  const notEnabledText =
    'This server has not enabled model connections (missing CREDENTIAL_ENCRYPTION_KEY).'

  const handleAdd = async () => {
    setMessage(null)
    try {
      await create.mutateAsync({
        label: label.trim(),
        kind,
        base_url: baseUrl.trim(),
        model: model.trim(),
        secret: secret.trim(),
      })
      setLabel('')
      setSecret('')
      setMessage({ kind: 'ok', text: 'Connection added.' })
    } catch (err) {
      const text =
        isApiError(err) && err.status === 503 ? notEnabledText : 'Could not add the connection.'
      setMessage({ kind: 'err', text })
    }
  }

  const handleRemove = async (id: string) => {
    setMessage(null)
    try {
      await remove.mutateAsync(id)
      setMessage({ kind: 'ok', text: 'Connection removed.' })
    } catch {
      setMessage({ kind: 'err', text: 'Could not remove the connection.' })
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Add one or more model connections — each with its own name, source, endpoint, model and key.
        Pick which one the assistant uses from the model menu in the chat panel. Keys are stored
        encrypted; only a masked hint is ever shown.
      </p>

      {connections && connections.length > 0 && (
        <div className="space-y-2">
          {connections.map((conn) => (
            <ConnectionRow
              key={conn.id}
              conn={conn}
              onRemove={() => void handleRemove(conn.id)}
              removing={remove.isPending}
            />
          ))}
        </div>
      )}

      <div className="space-y-2 rounded-md border border-border p-3">
        <h4 className="text-sm font-semibold">Add a connection</h4>

        <div className="flex flex-wrap gap-1.5">
          {Object.keys(PRESETS).map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => applyPreset(name)}
              className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground hover:bg-muted"
            >
              {name}
            </button>
          ))}
        </div>

        <input
          aria-label="Connection name"
          placeholder="Name (e.g. My Gemini)"
          className={inputClass}
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
        <select
          aria-label="Source type"
          className={inputClass}
          value={kind}
          onChange={(e) => setKind(e.target.value as ConnectionKind)}
        >
          <option value="openai_compatible">OpenAI-compatible (OpenAI, Gemini, Groq…)</option>
          <option value="ollama">Ollama (cloud or self-hosted)</option>
          <option value="codex">Codex subscription (auth.json)</option>
        </select>
        {kind !== 'codex' && (
          <>
            <input
              aria-label="Base URL"
              placeholder="Base URL"
              className={inputClass}
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
            <input
              aria-label="Model"
              placeholder="Model (e.g. gemini-2.5-flash-lite)"
              className={inputClass}
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
          </>
        )}
        <input
          aria-label="API key or token"
          type="password"
          autoComplete="off"
          placeholder={kind === 'codex' ? 'auth.json contents' : 'API key'}
          className={inputClass}
          value={secret}
          onChange={(e) => setSecret(e.target.value)}
        />
        <button
          type="button"
          onClick={() => void handleAdd()}
          disabled={!label.trim() || !secret.trim() || create.isPending}
          className={`flex items-center gap-1.5 ${submitClass}`}
        >
          {create.isPending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          Add connection
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
