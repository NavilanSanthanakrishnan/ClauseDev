import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { Check, Save, Settings, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { PageHeader } from '../components/PageHeader';
import { SectionFrame } from '../components/SectionFrame';
import { StatusBadge } from '../components/StatusBadge';
import { api, type OpenAISettings } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import { useDocumentTitle } from '../lib/useDocumentTitle';

type SettingsFormProps = {
  accessToken: string;
  queryClient: QueryClient;
  settings?: OpenAISettings;
};

function SettingsForm({ accessToken, queryClient, settings }: SettingsFormProps) {
  const [baseUrl, setBaseUrl] = useState(settings?.base_url ?? '');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState(settings?.model ?? '');

  const saveMutation = useMutation({
    mutationFn: () =>
      api.updateOpenAISettings(accessToken, {
        base_url: baseUrl || undefined,
        api_key: apiKey || undefined,
        model: model || undefined,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['openai-settings'] });
      setApiKey('');
    },
  });

  const clearMutation = useMutation({
    mutationFn: () => api.clearOpenAISettings(accessToken),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['openai-settings'] });
      setBaseUrl('');
      setApiKey('');
      setModel('');
    },
  });

  const s = settings;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Settings"
        title="Configure the AI model backend."
        description="Use any OpenAI-compatible endpoint alongside or instead of Codex OAuth. When both are configured, the OpenAI-compatible endpoint is tried first."
        badges={
          s?.enabled ? (
            <StatusBadge tone="success">OpenAI-compatible active</StatusBadge>
          ) : (
            <StatusBadge tone="neutral">Using Codex OAuth</StatusBadge>
          )
        }
      />

      <SectionFrame
        eyebrow="OpenAI-compatible endpoint"
        title="Custom model backend"
        description="Works with llama.cpp, Ollama, LM Studio, OpenAI, Anthropic-compatible proxies, or any server that speaks the OpenAI /chat/completions API."
        icon={Settings}
        actions={
          s?.enabled ? (
            <button
              type="button"
              className="button button-ghost"
              onClick={() => clearMutation.mutate()}
              disabled={clearMutation.isPending}
            >
              <Trash2 size={15} />
              {clearMutation.isPending ? 'Clearing…' : 'Clear saved settings'}
            </button>
          ) : undefined
        }
      >
        <div className="field-grid">
          <label className="field field-full">
            <span className="field-label">Base URL</span>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://localhost:8001/v1"
            />
          </label>
          <label className="field">
            <span className="field-label">
              API key{s?.api_key_set ? ' (saved — leave blank to keep current)' : ''}
            </span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={s?.api_key_set ? '••••••••' : 'sk-...  or  any-string'}
            />
          </label>
          <label className="field">
            <span className="field-label">Model name</span>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="gpt-4o  /  llama3  /  unsloth/GLM-4.7-Flash"
            />
          </label>
        </div>

        <div className="button-row">
          <button
            type="button"
            className="button button-primary"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || (!baseUrl.trim() && !apiKey.trim() && !model.trim())}
          >
            <Save size={15} />
            {saveMutation.isPending ? 'Saving…' : 'Save'}
          </button>
          {saveMutation.isSuccess ? (
            <span className="inline-note" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Check size={13} /> Saved
            </span>
          ) : null}
          {saveMutation.error instanceof Error ? (
            <span className="form-error">{saveMutation.error.message}</span>
          ) : null}
        </div>

        <div className="simple-list">
          <div className="simple-list-row">
            <strong>llama.cpp:</strong>
            <span><code className="md-inline-code">http://localhost:8001/v1</code> — any string as key — your model alias</span>
          </div>
          <div className="simple-list-row">
            <strong>Ollama:</strong>
            <span><code className="md-inline-code">http://localhost:11434/v1</code> — key <code className="md-inline-code">ollama</code> — e.g. <code className="md-inline-code">llama3.1</code></span>
          </div>
          <div className="simple-list-row">
            <strong>OpenAI:</strong>
            <span><code className="md-inline-code">https://api.openai.com/v1</code> — your <code className="md-inline-code">sk-…</code> key — e.g. <code className="md-inline-code">gpt-4o</code></span>
          </div>
          <div className="simple-list-row">
            <strong>Codex OAuth:</strong>
            <span>Still works when no endpoint is saved here. Run <code className="md-inline-code">codex login</code> as usual.</span>
          </div>
        </div>
      </SectionFrame>
    </div>
  );
}

export function SettingsPage() {
  useDocumentTitle('Settings');
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const settingsQuery = useQuery({
    queryKey: ['openai-settings'],
    queryFn: () => api.getOpenAISettings(accessToken!),
    enabled: Boolean(accessToken),
  });

  const settings = settingsQuery.data;
  const formKey = [settings?.base_url ?? '', settings?.model ?? '', settings?.api_key_set ? '1' : '0'].join('::');

  return (
    <SettingsForm
      key={formKey}
      accessToken={accessToken!}
      queryClient={queryClient}
      settings={settings}
    />
  );
}
