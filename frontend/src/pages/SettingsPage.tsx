import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Key, Trash2, Copy, Check, Loader2, ExternalLink, Info, Shield } from 'lucide-react'
import { adminApi } from '@/api/admin'
import type { ApiKeyInfo } from '@/api/admin'
import { setApiKey, clearApiKey } from '@/api/client'
import { cn, formatDate } from '@/lib/utils'

/* ------------------------------------------------------------------ */
/*  Tab Button                                                         */
/* ------------------------------------------------------------------ */

type TabId = 'api-keys' | 'llm' | 'about'

interface TabButtonProps {
  id: TabId
  label: string
  active: boolean
  onClick: () => void
}

function TabButton({ label, active, onClick }: TabButtonProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'border-b-2 px-4 py-2 text-sm font-medium transition-colors',
        active
          ? 'border-primary text-primary'
          : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground',
      )}
    >
      {label}
    </button>
  )
}

/* ------------------------------------------------------------------ */
/*  Your API Key Section                                               */
/* ------------------------------------------------------------------ */

function YourApiKeySection() {
  const stored = localStorage.getItem('lnc_api_key') ?? ''
  const [keyInput, setKeyInput] = useState(stored)
  const [masked, setMasked] = useState(true)
  const [saved, setSaved] = useState(false)

  function handleSet() {
    if (keyInput.trim()) {
      setApiKey(keyInput.trim())
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    }
  }

  function handleClear() {
    clearApiKey()
    setKeyInput('')
    setSaved(false)
  }

  const displayValue = masked && keyInput.length > 8
    ? keyInput.slice(0, 4) + '*'.repeat(keyInput.length - 8) + keyInput.slice(-4)
    : keyInput

  return (
    <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <Key className="h-5 w-5 text-primary" />
        <h3 className="text-lg font-semibold text-foreground">Your API Key</h3>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Set your API key to authenticate requests. Stored in browser localStorage.
      </p>

      <div className="mt-4 flex items-center gap-2">
        <div className="relative flex-1">
          <input
            type={masked ? 'password' : 'text'}
            value={masked ? displayValue : keyInput}
            onChange={(e) => {
              setMasked(false)
              setKeyInput(e.target.value)
            }}
            onFocus={() => setMasked(false)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 pr-16 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="Enter your API key"
          />
          {keyInput && (
            <button
              type="button"
              onClick={() => setMasked(!masked)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground"
            >
              {masked ? 'Show' : 'Hide'}
            </button>
          )}
        </div>
        <button
          onClick={handleSet}
          disabled={!keyInput.trim()}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saved ? <Check className="h-4 w-4" /> : null}
          {saved ? 'Saved' : 'Set'}
        </button>
        <button
          onClick={handleClear}
          className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-accent"
        >
          Clear
        </button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  API Key Management (Admin)                                         */
/* ------------------------------------------------------------------ */

function ApiKeyRow({ apiKey, onDelete }: { apiKey: ApiKeyInfo; onDelete: () => void }) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  return (
    <tr className="border-b border-border last:border-b-0">
      <td className="px-3 py-2.5 text-sm font-medium text-foreground">{apiKey.name}</td>
      <td className="px-3 py-2.5 text-sm">
        <span
          className={cn(
            'inline-flex rounded-full px-2 py-0.5 text-xs font-medium',
            apiKey.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800',
          )}
        >
          {apiKey.role}
        </span>
      </td>
      <td className="px-3 py-2.5 text-sm">
        <span
          className={cn(
            'inline-flex rounded-full px-2 py-0.5 text-xs font-medium',
            apiKey.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600',
          )}
        >
          {apiKey.enabled ? 'Active' : 'Disabled'}
        </span>
      </td>
      <td className="px-3 py-2.5 text-xs text-muted-foreground">{formatDate(apiKey.created_at)}</td>
      <td className="px-3 py-2.5 text-xs text-muted-foreground">{formatDate(apiKey.last_used_at)}</td>
      <td className="px-3 py-2.5 text-right">
        {confirmDelete ? (
          <span className="inline-flex items-center gap-1">
            <button
              onClick={onDelete}
              className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700"
            >
              Confirm
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="rounded px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
            >
              No
            </button>
          </span>
        ) : (
          <button
            onClick={() => setConfirmDelete(true)}
            className="rounded p-1 text-muted-foreground hover:bg-red-50 hover:text-red-600"
            title="Delete"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </td>
    </tr>
  )
}

function ManageApiKeysSection() {
  const queryClient = useQueryClient()
  const [newName, setNewName] = useState('')
  const [newRole, setNewRole] = useState('reader')
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const { data: apiKeys, isLoading, error } = useQuery({
    queryKey: ['api-keys'],
    queryFn: adminApi.listApiKeys,
  })

  const createMutation = useMutation({
    mutationFn: () => adminApi.createApiKey(newName.trim(), newRole),
    onSuccess: (response) => {
      setCreatedKey(response.api_key)
      setNewName('')
      setNewRole('reader')
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => adminApi.deleteApiKey(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
    },
  })

  function handleCopy() {
    if (createdKey) {
      navigator.clipboard.writeText(createdKey).catch(() => {
        // fallback: select text
      })
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <Shield className="h-5 w-5 text-primary" />
        <h3 className="text-lg font-semibold text-foreground">Manage API Keys</h3>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Create and manage API keys for accessing the platform.
      </p>

      {/* Created key banner */}
      {createdKey && (
        <div className="mt-4 rounded-md border border-yellow-300 bg-yellow-50 p-4">
          <div className="flex items-start gap-2">
            <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-yellow-700" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-yellow-800">
                API key created successfully. This key will only be shown once.
              </p>
              <div className="mt-2 flex items-center gap-2">
                <code className="block flex-1 overflow-x-auto rounded bg-yellow-100 px-3 py-1.5 font-mono text-sm text-yellow-900">
                  {createdKey}
                </code>
                <button
                  onClick={handleCopy}
                  className="inline-flex items-center gap-1 rounded-md border border-yellow-400 bg-white px-3 py-1.5 text-xs font-medium text-yellow-800 hover:bg-yellow-50"
                >
                  {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create key form */}
      <div className="mt-4 flex items-end gap-3">
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium text-foreground">Key Name</label>
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="e.g. CI Pipeline"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-foreground">Role</label>
          <select
            value={newRole}
            onChange={(e) => setNewRole(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="reader">reader</option>
            <option value="admin">admin</option>
          </select>
        </div>
        <button
          onClick={() => createMutation.mutate()}
          disabled={!newName.trim() || createMutation.isPending}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {createMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
          Create
        </button>
      </div>
      {createMutation.isError && (
        <p className="mt-2 text-sm text-red-600">
          Error: {(createMutation.error as Error).message}
        </p>
      )}

      {/* Keys table */}
      {isLoading && (
        <div className="mt-6 flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading API keys...
        </div>
      )}
      {error && (
        <p className="mt-4 text-sm text-red-600">
          Failed to load API keys: {(error as Error).message}
        </p>
      )}

      {apiKeys && apiKeys.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-md border border-border">
          <table className="w-full text-left">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Name</th>
                <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Role</th>
                <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Status</th>
                <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Created</th>
                <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">Last Used</th>
                <th className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground"></th>
              </tr>
            </thead>
            <tbody>
              {apiKeys.map((k) => (
                <ApiKeyRow
                  key={k.id}
                  apiKey={k}
                  onDelete={() => deleteMutation.mutate(k.id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
      {apiKeys && apiKeys.length === 0 && (
        <p className="mt-4 text-sm text-muted-foreground">No API keys found.</p>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  LLM Configuration Section                                          */
/* ------------------------------------------------------------------ */

function LlmConfigSection() {
  return (
    <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
      <h3 className="text-lg font-semibold text-foreground">LLM Configuration</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        LLM provider configuration coming soon. Currently configured via environment variables.
      </p>

      <div className="mt-4 rounded-md bg-muted/50 p-4">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Environment Variables
        </p>
        <div className="mt-2 space-y-1.5">
          <div className="flex items-center gap-2 text-sm">
            <code className="rounded bg-muted px-2 py-0.5 font-mono text-xs text-foreground">LLM_BASE_URL</code>
            <span className="text-muted-foreground">- Base URL for the LLM API endpoint</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <code className="rounded bg-muted px-2 py-0.5 font-mono text-xs text-foreground">LLM_MODEL</code>
            <span className="text-muted-foreground">- Model identifier to use for inference</span>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  About Section                                                      */
/* ------------------------------------------------------------------ */

function AboutSection() {
  return (
    <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
      <h3 className="text-lg font-semibold text-foreground">About</h3>

      <div className="mt-3 space-y-2 text-sm text-muted-foreground">
        <p>
          <span className="font-medium text-foreground">Logistics News Dashboard</span>{' '}
          v0.1.0
        </p>
        <p>
          Real-time logistics news aggregation and analysis platform with AI-powered insights.
        </p>
      </div>

      <div className="mt-4">
        <a
          href="/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
        >
          <ExternalLink className="h-4 w-4" />
          API Documentation
        </a>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('api-keys')

  return (
    <div>
      <h2 className="text-2xl font-bold text-foreground">Settings</h2>

      {/* Tabs */}
      <div className="mt-4 flex gap-0 border-b border-border">
        <TabButton id="api-keys" label="API Keys" active={activeTab === 'api-keys'} onClick={() => setActiveTab('api-keys')} />
        <TabButton id="llm" label="LLM Config" active={activeTab === 'llm'} onClick={() => setActiveTab('llm')} />
        <TabButton id="about" label="About" active={activeTab === 'about'} onClick={() => setActiveTab('about')} />
      </div>

      {/* Tab content */}
      <div className="mt-6 space-y-6">
        {activeTab === 'api-keys' && (
          <>
            <YourApiKeySection />
            <ManageApiKeysSection />
          </>
        )}
        {activeTab === 'llm' && <LlmConfigSection />}
        {activeTab === 'about' && <AboutSection />}
      </div>
    </div>
  )
}
