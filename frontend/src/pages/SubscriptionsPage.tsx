import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Pencil, Trash2, X, Loader2 } from 'lucide-react'
import { subscriptionsApi } from '@/api/subscriptions'
import type { Subscription, SubscriptionInput } from '@/api/subscriptions'
import { Badge } from '@/components/common/Badge'
import { cn, formatDate } from '@/lib/utils'

const TRANSPORT_MODES = ['ocean', 'air', 'road', 'rail'] as const
const LANGUAGES = ['en', 'zh'] as const
const CHANNELS = ['websocket', 'webhook'] as const
const FREQUENCIES = ['realtime', 'daily', 'weekly'] as const
const URGENCY_LEVELS = ['high', 'medium', 'low'] as const

function emptyForm(): SubscriptionInput {
  return {
    name: '',
    channel: 'websocket',
    frequency: 'realtime',
    transport_modes: [],
    topics: [],
    regions: [],
    languages: [],
    urgency_min: undefined,
    channel_config: {},
    enabled: true,
  }
}

function subscriptionToForm(sub: Subscription): SubscriptionInput {
  return {
    name: sub.name,
    channel: sub.channel,
    frequency: sub.frequency,
    transport_modes: sub.transport_modes ?? [],
    topics: sub.topics ?? [],
    regions: sub.regions ?? [],
    languages: sub.languages ?? [],
    urgency_min: sub.urgency_min,
    channel_config: sub.channel_config ?? {},
    enabled: sub.enabled,
  }
}

/* ------------------------------------------------------------------ */
/*  Subscription Form                                                  */
/* ------------------------------------------------------------------ */

interface SubscriptionFormProps {
  initial: SubscriptionInput
  onSave: (data: SubscriptionInput) => void
  onCancel: () => void
  saving: boolean
  title: string
}

function SubscriptionForm({ initial, onSave, onCancel, saving, title }: SubscriptionFormProps) {
  const [form, setForm] = useState<SubscriptionInput>(initial)
  const [topicsText, setTopicsText] = useState((initial.topics ?? []).join(', '))
  const [regionsText, setRegionsText] = useState((initial.regions ?? []).join(', '))

  function patch(updates: Partial<SubscriptionInput>) {
    setForm((prev) => ({ ...prev, ...updates }))
  }

  function toggleArrayItem(field: 'transport_modes' | 'languages', value: string) {
    const current = form[field] ?? []
    const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value]
    patch({ [field]: next })
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const topics = topicsText
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    const regions = regionsText
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    onSave({ ...form, topics, regions })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-border bg-card p-5 shadow-sm"
    >
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-foreground">{title}</h3>
        <button type="button" onClick={onCancel} className="text-muted-foreground hover:text-foreground">
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {/* Name */}
        <div className="sm:col-span-2">
          <label className="mb-1 block text-sm font-medium text-foreground">Name</label>
          <input
            type="text"
            required
            value={form.name}
            onChange={(e) => patch({ name: e.target.value })}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="My subscription"
          />
        </div>

        {/* Channel */}
        <div>
          <label className="mb-1 block text-sm font-medium text-foreground">Channel</label>
          <select
            value={form.channel}
            onChange={(e) => patch({ channel: e.target.value })}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {CHANNELS.map((ch) => (
              <option key={ch} value={ch}>
                {ch}
              </option>
            ))}
          </select>
        </div>

        {/* Frequency */}
        <div>
          <label className="mb-1 block text-sm font-medium text-foreground">Frequency</label>
          <select
            value={form.frequency ?? 'realtime'}
            onChange={(e) => patch({ frequency: e.target.value })}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            {FREQUENCIES.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>

        {/* Webhook config (conditional) */}
        {form.channel === 'webhook' && (
          <>
            <div>
              <label className="mb-1 block text-sm font-medium text-foreground">Webhook URL</label>
              <input
                type="url"
                value={form.channel_config?.url ?? ''}
                onChange={(e) =>
                  patch({ channel_config: { ...form.channel_config, url: e.target.value } })
                }
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="https://example.com/webhook"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-foreground">Webhook Secret</label>
              <input
                type="text"
                value={form.channel_config?.secret ?? ''}
                onChange={(e) =>
                  patch({ channel_config: { ...form.channel_config, secret: e.target.value } })
                }
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="optional secret"
              />
            </div>
          </>
        )}

        {/* Transport Modes */}
        <div className="sm:col-span-2">
          <label className="mb-1.5 block text-sm font-medium text-foreground">Transport Modes</label>
          <div className="flex flex-wrap gap-3">
            {TRANSPORT_MODES.map((mode) => (
              <label key={mode} className="flex items-center gap-1.5 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={(form.transport_modes ?? []).includes(mode)}
                  onChange={() => toggleArrayItem('transport_modes', mode)}
                  className="rounded border-border"
                />
                {mode}
              </label>
            ))}
          </div>
        </div>

        {/* Topics */}
        <div>
          <label className="mb-1 block text-sm font-medium text-foreground">Topics (comma separated)</label>
          <input
            type="text"
            value={topicsText}
            onChange={(e) => setTopicsText(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="port congestion, tariffs"
          />
        </div>

        {/* Regions */}
        <div>
          <label className="mb-1 block text-sm font-medium text-foreground">Regions (comma separated)</label>
          <input
            type="text"
            value={regionsText}
            onChange={(e) => setRegionsText(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="Asia, Europe"
          />
        </div>

        {/* Languages */}
        <div>
          <label className="mb-1.5 block text-sm font-medium text-foreground">Languages</label>
          <div className="flex flex-wrap gap-3">
            {LANGUAGES.map((lang) => (
              <label key={lang} className="flex items-center gap-1.5 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={(form.languages ?? []).includes(lang)}
                  onChange={() => toggleArrayItem('languages', lang)}
                  className="rounded border-border"
                />
                {lang.toUpperCase()}
              </label>
            ))}
          </div>
        </div>

        {/* Urgency Min */}
        <div>
          <label className="mb-1 block text-sm font-medium text-foreground">Minimum Urgency</label>
          <select
            value={form.urgency_min ?? ''}
            onChange={(e) => patch({ urgency_min: e.target.value || undefined })}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="">Any</option>
            {URGENCY_LEVELS.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </div>

        {/* Enabled */}
        <div className="flex items-center gap-2 sm:col-span-2">
          <label className="flex items-center gap-2 text-sm font-medium text-foreground">
            <input
              type="checkbox"
              checked={form.enabled ?? true}
              onChange={(e) => patch({ enabled: e.target.checked })}
              className="rounded border-border"
            />
            Enabled
          </label>
        </div>
      </div>

      {/* Actions */}
      <div className="mt-5 flex items-center gap-3">
        <button
          type="submit"
          disabled={saving || !form.name.trim()}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saving && <Loader2 className="h-4 w-4 animate-spin" />}
          Save
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

/* ------------------------------------------------------------------ */
/*  Subscription Card                                                  */
/* ------------------------------------------------------------------ */

interface SubscriptionCardProps {
  sub: Subscription
  onEdit: () => void
  onDelete: () => void
  onToggle: (enabled: boolean) => void
  deleting: boolean
  toggling: boolean
}

function SubscriptionCard({ sub, onEdit, onDelete, onToggle, deleting, toggling }: SubscriptionCardProps) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-foreground">{sub.name}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Created {formatDate(sub.created_at)}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={onEdit}
            className="rounded p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            title="Edit"
          >
            <Pencil className="h-4 w-4" />
          </button>
          {confirmDelete ? (
            <div className="flex items-center gap-1">
              <button
                onClick={onDelete}
                disabled={deleting}
                className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? 'Deleting...' : 'Confirm'}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="rounded px-2 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
              >
                No
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              className="rounded p-1.5 text-muted-foreground hover:bg-red-50 hover:text-red-600"
              title="Delete"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Badges row */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <Badge variant={sub.channel === 'webhook' ? 'warning' : 'info'}>{sub.channel}</Badge>
        <Badge variant="outline">{sub.frequency}</Badge>
        {sub.urgency_min && (
          <Badge variant={sub.urgency_min === 'high' ? 'negative' : sub.urgency_min === 'medium' ? 'warning' : 'positive'}>
            min: {sub.urgency_min}
          </Badge>
        )}
      </div>

      {/* Filter summary */}
      {((sub.transport_modes && sub.transport_modes.length > 0) ||
        (sub.topics && sub.topics.length > 0) ||
        (sub.regions && sub.regions.length > 0)) && (
        <div className="mt-2 flex flex-wrap items-center gap-1">
          {sub.transport_modes?.map((m) => (
            <span
              key={m}
              className="inline-flex items-center rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground"
            >
              {m}
            </span>
          ))}
          {sub.topics?.map((t) => (
            <span
              key={t}
              className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
            >
              {t}
            </span>
          ))}
          {sub.regions?.map((r) => (
            <span
              key={r}
              className="inline-flex items-center rounded-full bg-purple-50 px-2 py-0.5 text-xs text-purple-700"
            >
              {r}
            </span>
          ))}
        </div>
      )}

      {/* Enabled toggle */}
      <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
        <label className="flex items-center gap-2 text-sm text-foreground">
          <input
            type="checkbox"
            checked={sub.enabled}
            disabled={toggling}
            onChange={(e) => onToggle(e.target.checked)}
            className="rounded border-border"
          />
          <span className={cn(sub.enabled ? 'text-green-700' : 'text-muted-foreground')}>
            {sub.enabled ? 'Enabled' : 'Disabled'}
          </span>
        </label>
        {sub.languages && sub.languages.length > 0 && (
          <div className="flex gap-1">
            {sub.languages.map((l) => (
              <Badge key={l} variant="outline">
                {l.toUpperCase()}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function SubscriptionsPage() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)

  // ------- queries / mutations ------- //
  const { data: subscriptions, isLoading, error } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: subscriptionsApi.list,
  })

  const createMutation = useMutation({
    mutationFn: (data: SubscriptionInput) => subscriptionsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      setShowForm(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<SubscriptionInput> }) =>
      subscriptionsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
      setEditingId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => subscriptionsApi.del(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subscriptions'] })
    },
  })

  // ------- render ------- //
  const editingSub = editingId ? subscriptions?.find((s) => s.id === editingId) : null

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-foreground">Subscriptions</h2>
        <button
          onClick={() => {
            setEditingId(null)
            setShowForm(true)
          }}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          New Subscription
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="mt-4">
          <SubscriptionForm
            title="New Subscription"
            initial={emptyForm()}
            onSave={(data) => createMutation.mutate(data)}
            onCancel={() => setShowForm(false)}
            saving={createMutation.isPending}
          />
          {createMutation.isError && (
            <p className="mt-2 text-sm text-red-600">
              Error: {(createMutation.error as Error).message}
            </p>
          )}
        </div>
      )}

      {/* Edit form (inline panel) */}
      {editingSub && (
        <div className="mt-4">
          <SubscriptionForm
            title={`Edit: ${editingSub.name}`}
            initial={subscriptionToForm(editingSub)}
            onSave={(data) => updateMutation.mutate({ id: editingSub.id, data })}
            onCancel={() => setEditingId(null)}
            saving={updateMutation.isPending}
          />
          {updateMutation.isError && (
            <p className="mt-2 text-sm text-red-600">
              Error: {(updateMutation.error as Error).message}
            </p>
          )}
        </div>
      )}

      {/* Loading / Error */}
      {isLoading && (
        <div className="mt-8 flex items-center justify-center gap-2 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          Loading subscriptions...
        </div>
      )}
      {error && (
        <p className="mt-4 text-sm text-red-600">
          Failed to load subscriptions: {(error as Error).message}
        </p>
      )}

      {/* Subscription list */}
      {subscriptions && subscriptions.length === 0 && !showForm && (
        <p className="mt-8 text-center text-muted-foreground">
          No subscriptions yet. Create one to get started.
        </p>
      )}

      {subscriptions && subscriptions.length > 0 && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {subscriptions.map((sub) => (
            <SubscriptionCard
              key={sub.id}
              sub={sub}
              onEdit={() => {
                setShowForm(false)
                setEditingId(sub.id)
              }}
              onDelete={() => deleteMutation.mutate(sub.id)}
              onToggle={(enabled) =>
                updateMutation.mutate({ id: sub.id, data: { enabled } })
              }
              deleting={deleteMutation.isPending}
              toggling={updateMutation.isPending}
            />
          ))}
        </div>
      )}
    </div>
  )
}
