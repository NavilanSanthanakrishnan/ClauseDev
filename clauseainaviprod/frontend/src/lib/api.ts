export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001/api';

export type SearchMode = 'standard' | 'agentic';

export type SearchFilters = {
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

export type FilterOptions = {
  jurisdictions: string[];
  sessions: string[];
  statuses: string[];
  outcomes: string[];
  topics: string[];
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
  getFilters: () => request<FilterOptions>('/filters'),
  getBill: (billId: string) => request<BillDetail>(`/bills/${encodeURIComponent(billId)}`),
  search: (mode: SearchMode, query: string, filters: SearchFilters) =>
    request<SearchResponse>(`/search/${mode}`, {
      method: 'POST',
      body: JSON.stringify({ query, filters }),
    }),
};

