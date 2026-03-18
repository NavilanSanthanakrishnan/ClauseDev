export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export type User = {
  user_id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_admin: boolean;
};

export type AuthResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
};

export type Project = {
  project_id: string;
  title: string;
  jurisdiction_type: string;
  jurisdiction_name: string;
  status: string;
  current_stage: string;
  created_at: string;
  updated_at: string;
};

export type PipelineRun = {
  run_id: string;
  project_id: string;
  stage_name: string;
  status: string;
  attempt_count: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_summary: string | null;
};

export type Metadata = {
  title: string;
  description: string;
  summary: string;
  keywords: string[];
  extras: Record<string, unknown>;
};

export type Artifact = {
  artifact_id: string;
  stage_name: string;
  artifact_kind: string;
  status: string;
  markdown_content: string;
  payload_json: Record<string, unknown>;
};

export type Draft = {
  draft_id: string;
  current_text: string;
  title: string;
};

export type DraftVersion = {
  version_id: string;
  version_number: number;
  source_kind: string;
  content_text: string;
  change_summary: Record<string, unknown>;
  created_at: string;
};

export type Suggestion = {
  suggestion_id: string;
  stage_name: string;
  title: string;
  rationale: string;
  before_text: string;
  after_text: string;
  source_refs: Array<Record<string, unknown>>;
  status: string;
};

export type AgentPass = {
  artifact_id: string;
  markdown_content: string;
  payload_json: Record<string, unknown>;
  suggestion_count: number;
};

export type EditorSession = {
  session_id: string;
  project_id: string;
  thread_id: string;
  active_turn_id: string;
  status: string;
  current_stage: string;
  workspace_dir: string;
  latest_agent_message: string;
  final_message: string;
  current_diff: string;
  completion_summary: string;
  error_message: string;
  pending_approval: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type EditorSessionEvent = {
  event_id: string;
  session_id: string;
  project_id: string;
  kind: string;
  title: string;
  body: string;
  phase: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type BillSearchItem = {
  bill_id: string;
  identifier: string | null;
  title: string | null;
  summary_text: string | null;
  jurisdiction_name: string | null;
  state_code: string | null;
  derived_status: string | null;
  latest_action_date: string | null;
  primary_source_url: string | null;
};

export type BillDetail = BillSearchItem & {
  session_identifier: string | null;
  latest_passage_date: string | null;
  full_text: string | null;
};

export type LawSearchItem = {
  document_id: string;
  citation: string | null;
  heading: string | null;
  jurisdiction: string | null;
  hierarchy_path: string | null;
  source_url: string | null;
  body_excerpt: string | null;
};

export type LawDetail = {
  document_id: string;
  citation: string | null;
  heading: string | null;
  jurisdiction: string | null;
  hierarchy_path: string | null;
  source_url: string | null;
  body_text: string | null;
};

export type ReferenceStatus = {
  bills_ready: boolean;
  laws_ready: boolean;
  bill_count: number | null;
  law_count: number | null;
};

export type ChatThread = {
  thread_id: string;
  project_id: string | null;
  title: string;
  scope: string;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  message_id: string;
  role: string;
  content: string;
  citations: Array<Record<string, unknown>>;
  created_at: string;
};

export type OpenAISettings = {
  base_url: string;
  api_key_set: boolean;
  model: string;
  enabled: boolean;
};

type RequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  token?: string | null;
  body?: unknown;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Request failed with ${response.status}`);
  }

  if (response.status === 204) {
    return null as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  signup: (payload: { email: string; password: string; display_name?: string }) =>
    request<AuthResponse>('/auth/signup', { method: 'POST', body: payload }),
  login: (payload: { email: string; password: string }) =>
    request<AuthResponse>('/auth/login', { method: 'POST', body: payload }),
  me: (token: string) => request<User>('/auth/me', { token }),
  logout: (refreshToken: string) =>
    request<void>('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken } }),
  listProjects: (token: string) => request<Project[]>('/api/projects', { token }),
  createProject: (
    token: string,
    payload: { title: string; jurisdiction_type: string; jurisdiction_name: string; initial_text?: string },
  ) => request<Project>('/api/projects', { method: 'POST', token, body: payload }),
  referenceStatus: (token: string) => request<ReferenceStatus>('/api/reference/status', { token }),
  listPipelineRuns: (token: string, projectId: string) =>
    request<PipelineRun[]>(`/api/projects/${projectId}/pipeline-runs`, { token }),
  searchBills: (token: string, query: string, filters?: { status?: string; stateCode?: string }) =>
    request<{ items: BillSearchItem[] }>(
      `/api/reference/bills?q=${encodeURIComponent(query)}&status=${encodeURIComponent(filters?.status ?? '')}&state_code=${encodeURIComponent(filters?.stateCode ?? '')}`,
      { token },
    ),
  getBillDetail: (token: string, billId: string) =>
    request<BillDetail>(`/api/reference/bills/${encodeURIComponent(billId)}`, { token }),
  searchLaws: (token: string, query: string, filters?: { jurisdiction?: string }) =>
    request<{ items: LawSearchItem[] }>(
      `/api/reference/laws?q=${encodeURIComponent(query)}&jurisdiction=${encodeURIComponent(filters?.jurisdiction ?? '')}`,
      { token },
    ),
  getLawDetail: (token: string, documentId: string) =>
    request<LawDetail>(`/api/reference/laws/${encodeURIComponent(documentId)}`, { token }),
  uploadSourceDocument: async (token: string, projectId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/source-document`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });
    if (!response.ok) {
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.detail ?? `Request failed with ${response.status}`);
    }
    return response.json() as Promise<{
      document_id: string;
      filename: string;
      file_type: string;
      extracted_text: string;
    }>;
  },
  getLatestSourceDocument: (token: string, projectId: string) =>
    request<{ document_id: string | null; filename: string | null; file_type: string | null; extracted_text: string }>(
      `/api/projects/${projectId}/source-document/latest`,
      { token },
    ),
  generateMetadata: (token: string, projectId: string) =>
    request<Metadata>(`/api/projects/${projectId}/metadata/generate`, {
      method: 'POST',
      token,
    }),
  getMetadata: (token: string, projectId: string) =>
    request<Metadata>(`/api/projects/${projectId}/metadata`, { token }),
  updateMetadata: (
    token: string,
    projectId: string,
    payload: { title: string; description: string; summary: string; keywords: string[]; extras?: Record<string, unknown> },
  ) =>
    request<Metadata>(`/api/projects/${projectId}/metadata`, {
      method: 'PUT',
      token,
      body: payload,
    }),
  generateAnalysis: (token: string, projectId: string, stageName: string) =>
    request<Artifact>(`/api/projects/${projectId}/analysis/${stageName}`, {
      method: 'POST',
      token,
    }),
  getAnalysis: (token: string, projectId: string, stageName: string) =>
    request<Artifact>(`/api/projects/${projectId}/analysis/${stageName}`, { token }),
  getSuggestions: (token: string, projectId: string, stageName: string) =>
    request<Suggestion[]>(`/api/projects/${projectId}/suggestions/${stageName}`, { token }),
  getAllSuggestions: (token: string, projectId: string) =>
    request<Suggestion[]>(`/api/projects/${projectId}/suggestions`, { token }),
  getDraft: (token: string, projectId: string) => request<Draft>(`/api/projects/${projectId}/draft`, { token }),
  listDraftVersions: (token: string, projectId: string) =>
    request<DraftVersion[]>(`/api/projects/${projectId}/draft/versions`, { token }),
  saveDraftVersion: (token: string, projectId: string, payload: { content_text: string; change_reason: string }) =>
    request<DraftVersion>(`/api/projects/${projectId}/draft/versions`, {
      method: 'POST',
      token,
      body: payload,
    }),
  restoreDraftVersion: (token: string, projectId: string, versionId: string) =>
    request<DraftVersion>(`/api/projects/${projectId}/draft/versions/${versionId}/restore`, {
      method: 'POST',
      token,
    }),
  applySuggestion: (
    token: string,
    projectId: string,
    suggestionId: string,
    payload?: { after_text?: string; change_reason?: string },
  ) =>
    request<Suggestion>(`/api/projects/${projectId}/suggestion-items/${suggestionId}/apply`, {
      method: 'POST',
      token,
      body: payload ?? {},
    }),
  rejectSuggestion: (token: string, projectId: string, suggestionId: string) =>
    request<Suggestion>(`/api/projects/${projectId}/suggestion-items/${suggestionId}/reject`, {
      method: 'POST',
      token,
    }),
  runEditorAgentPass: (token: string, projectId: string) =>
    request<AgentPass>(`/api/projects/${projectId}/editor/agent-pass`, {
      method: 'POST',
      token,
    }),
  startEditorSession: (token: string, projectId: string) =>
    request<EditorSession>(`/api/projects/${projectId}/editor/session`, {
      method: 'POST',
      token,
    }),
  getEditorSession: (token: string, projectId: string) =>
    request<EditorSession | null>(`/api/projects/${projectId}/editor/session`, { token }),
  listEditorSessionEvents: (token: string, projectId: string) =>
    request<EditorSessionEvent[]>(`/api/projects/${projectId}/editor/session/events`, { token }),
  steerEditorSession: (token: string, projectId: string, payload: { message: string }) =>
    request<EditorSession>(`/api/projects/${projectId}/editor/session/steer`, {
      method: 'POST',
      token,
      body: payload,
    }),
  approveEditorDiff: (token: string, projectId: string) =>
    request<EditorSession>(`/api/projects/${projectId}/editor/session/approve`, {
      method: 'POST',
      token,
    }),
  rejectEditorDiff: (token: string, projectId: string) =>
    request<EditorSession>(`/api/projects/${projectId}/editor/session/reject`, {
      method: 'POST',
      token,
    }),
  startPipelineRun: (token: string, projectId: string, stageName: string) =>
    request(`/api/projects/${projectId}/pipeline-runs`, {
      method: 'POST',
      token,
      body: { stage_name: stageName },
    }),
  downloadDraft: async (token: string, projectId: string, format: 'txt' | 'docx') => {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/export/${format}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) {
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.detail ?? `Request failed with ${response.status}`);
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    const disposition = response.headers.get('Content-Disposition') ?? '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    anchor.href = url;
    anchor.download = match?.[1] ?? `draft.${format}`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(url);
  },
  listChatThreads: (token: string) => request<ChatThread[]>('/api/chat/threads', { token }),
  createChatThread: (token: string, payload: { title: string; project_id?: string | null }) =>
    request<ChatThread>('/api/chat/threads', { method: 'POST', token, body: payload }),
  listChatMessages: (token: string, threadId: string) =>
    request<ChatMessage[]>(`/api/chat/threads/${threadId}/messages`, { token }),
  createChatMessage: (token: string, threadId: string, payload: { content: string }) =>
    request<ChatMessage[]>(`/api/chat/threads/${threadId}/messages`, {
      method: 'POST',
      token,
      body: payload,
    }),
  getOpenAISettings: (token: string) =>
    request<OpenAISettings>('/api/settings/openai', { token }),
  updateOpenAISettings: (
    token: string,
    payload: { base_url?: string; api_key?: string; model?: string },
  ) =>
    request<OpenAISettings>('/api/settings/openai', { method: 'PUT', token, body: payload }),
  clearOpenAISettings: (token: string) =>
    request<{ success: boolean }>('/api/settings/openai', { method: 'DELETE', token }),

};
