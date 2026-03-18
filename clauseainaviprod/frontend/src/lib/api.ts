export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001/api';

export type SearchMode = 'standard' | 'agentic';
export type WorkspaceMode = 'bills' | 'laws';

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

export type SearchResponse = {
  mode: SearchMode;
  query: string;
  explanation: string;
  plan: Record<string, unknown>;
  items: BillListItem[];
};

export type StatsResponse = {
  total_bills: number;
  jurisdictions: number;
  active_sessions: number;
  top_topics: string[];
};

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

export type LawStatsResponse = {
  total_laws: number;
  california_laws: number;
  federal_laws: number;
};

export type LawFilterOptions = {
  jurisdictions: string[];
  sources: string[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'content-type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getStats: () => request<StatsResponse>('/stats'),
  getFilters: () => request<BillFilterOptions>('/filters'),
  getBill: (billId: string) => request<BillDetail>(`/bills/${encodeURIComponent(billId)}`),
  search: (mode: SearchMode, query: string, filters: BillSearchFilters) =>
    request<SearchResponse>(`/search/${mode}`, {
      method: 'POST',
      body: JSON.stringify({ query, filters }),
    }),
  getLawStats: () => request<LawStatsResponse>('/laws/stats'),
  getLawFilters: () => request<LawFilterOptions>('/laws/filters'),
  getLaw: (documentId: string) => request<LawDetail>(`/laws/${encodeURIComponent(documentId)}`),
  searchLaws: (mode: SearchMode, query: string, filters: LawSearchFilters) =>
    request<LawSearchResponse>(`/laws/search/${mode}`, {
      method: 'POST',
      body: JSON.stringify({ query, filters }),
    }),
};
