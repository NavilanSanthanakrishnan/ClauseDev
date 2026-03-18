export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001/api';

export type SearchMode = 'standard' | 'agentic';
export type RouteKey = 'home' | 'bill-lookup' | 'law-lookup' | 'workspace';
export type WorkspaceMode = 'bills' | 'laws';

export type User = {
  user_id: string;
  email: string;
  display_name: string;
};

export type AuthConfig = {
  enabled: boolean;
};

export type LoginResponse = {
  token: string;
  user: User;
};

export type BillSearchFilters = {
  jurisdiction?: string;
  session?: string;
  status?: string;
  topic?: string;
  outcome?: string;
  sort: 'relevance' | 'recent';
  limit: number;
};

export type BillListItem = {
  bill_id: string;
  identifier: string;
  jurisdiction: string;
  state_code: string;
  title: string;
  summary: string;
  status: string;
  outcome: string;
  sponsor: string;
  committee: string;
  session_name: string;
  source_url?: string | null;
  topics: string[];
  matched_reasons: string[];
  relevance_score: number;
};

export type BillDetail = BillListItem & {
  full_text: string;
  latest_action_date?: string | null;
};

export type BillSearchResponse = {
  mode: SearchMode;
  query: string;
  explanation: string;
  plan: Record<string, unknown>;
  items: BillListItem[];
};

export type SearchResponse = BillSearchResponse;

export type BillStats = {
  total_bills: number;
  jurisdictions: number;
  active_sessions: number;
  top_topics: string[];
};

export type StatsResponse = BillStats;

export type BillFilterOptions = {
  jurisdictions: string[];
  sessions: string[];
  statuses: string[];
  outcomes: string[];
  topics: string[];
};

export type LawSearchFilters = {
  jurisdiction?: string;
  source?: string;
  sort: 'relevance' | 'recent';
  limit: number;
};

export type LawListItem = {
  document_id: string;
  citation: string;
  jurisdiction: string;
  source: string;
  heading?: string | null;
  hierarchy_path?: string | null;
  body_excerpt?: string | null;
  source_url?: string | null;
  matched_reasons: string[];
  relevance_score: number;
};

export type LawDetail = LawListItem & {
  body_text: string;
};

export type LawSearchResponse = {
  mode: SearchMode;
  query: string;
  explanation: string;
  plan: Record<string, unknown>;
  items: LawListItem[];
};

export type LawStats = {
  total_laws: number;
  california_laws: number;
  federal_laws: number;
};

export type LawStatsResponse = LawStats;

export type LawFilterOptions = {
  jurisdictions: string[];
  sources: string[];
};

export type ProjectListItem = {
  project_id: string;
  title: string;
  policy_goal: string;
  jurisdiction?: string | null;
  status: string;
  stage: string;
  summary: string;
  created_at: string;
  updated_at: string;
};

export type ProjectDetail = ProjectListItem & {
  bill_text: string;
  insights: Record<string, ProjectInsightEnvelope>;
  messages: ProjectMessage[];
};

export type ProjectInsightEnvelope = {
  payload: Record<string, unknown>;
  updated_at: string;
};

export type ProjectMessage = {
  message_id: string;
  role: string;
  content: string;
  tool_trace: Array<Record<string, unknown>>;
  created_at: string;
};

export type CreateProjectInput = {
  title: string;
  policy_goal: string;
  jurisdiction?: string;
};

export type UpdateProjectInput = {
  title?: string;
  policy_goal?: string;
  jurisdiction?: string;
  status?: string;
  stage?: string;
  summary?: string;
  bill_text?: string;
};

export type RefreshInsightsResponse = {
  similar_bills: BillSearchResponse;
  conflicting_laws: LawSearchResponse;
  stakeholders: Record<string, unknown>;
  drafting_focus: Record<string, unknown>;
};

export type AgentResponse = {
  message: ProjectMessage;
  tool_trace: Array<Record<string, unknown>>;
  suggested_stage?: string | null;
  suggested_status?: string | null;
  revision_excerpt?: string | null;
};

type RequestOptions = RequestInit & {
  token?: string | null;
};

async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'content-type': 'application/json',
      ...(init?.token ? { authorization: `Bearer ${init.token}` } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail ?? `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getAuthConfig: () => request<AuthConfig>('/auth/config'),
  login: (email: string, password: string) =>
    request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  me: (token: string | null) => request<User>('/auth/me', { token }),
  logout: (token: string | null) => request<{ ok: boolean }>('/auth/logout', { method: 'POST', token }),

  getBillStats: (token: string | null) => request<BillStats>('/stats', { token }),
  getBillFilters: (token: string | null) => request<BillFilterOptions>('/filters', { token }),
  searchBills: (mode: SearchMode, query: string, filters: BillSearchFilters, token: string | null) =>
    request<BillSearchResponse>(`/search/${mode}`, {
      method: 'POST',
      token,
      body: JSON.stringify({ query, filters }),
    }),
  getBill: (billId: string, token: string | null) =>
    request<BillDetail>(`/bills/${encodeURIComponent(billId)}`, { token }),

  getLawStats: (token: string | null) => request<LawStats>('/laws/stats', { token }),
  getLawFilters: (token: string | null) => request<LawFilterOptions>('/laws/filters', { token }),
  searchLaws: (mode: SearchMode, query: string, filters: LawSearchFilters, token: string | null) =>
    request<LawSearchResponse>(`/laws/search/${mode}`, {
      method: 'POST',
      token,
      body: JSON.stringify({ query, filters }),
    }),
  getLaw: (documentId: string, token: string | null) =>
    request<LawDetail>(`/laws/${encodeURIComponent(documentId)}`, { token }),

  listProjects: (token: string | null) => request<ProjectListItem[]>('/projects', { token }),
  createProject: (payload: CreateProjectInput, token: string | null) =>
    request<ProjectDetail>('/projects', {
      method: 'POST',
      token,
      body: JSON.stringify(payload),
    }),
  getProject: (projectId: string, token: string | null) =>
    request<ProjectDetail>(`/projects/${encodeURIComponent(projectId)}`, { token }),
  updateProject: (projectId: string, payload: UpdateProjectInput, token: string | null) =>
    request<ProjectDetail>(`/projects/${encodeURIComponent(projectId)}`, {
      method: 'PUT',
      token,
      body: JSON.stringify(payload),
    }),
  refreshInsights: (projectId: string, token: string | null) =>
    request<RefreshInsightsResponse>(`/projects/${encodeURIComponent(projectId)}/insights/refresh`, {
      method: 'POST',
      token,
    }),
  agentChat: (projectId: string, message: string, token: string | null) =>
    request<AgentResponse>(`/projects/${encodeURIComponent(projectId)}/agent`, {
      method: 'POST',
      token,
      body: JSON.stringify({ message }),
    }),
};
