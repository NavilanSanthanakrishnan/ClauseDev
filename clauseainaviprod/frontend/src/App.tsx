import { useEffect, useState } from 'react';

import { AppShell } from './components/AppShell';
import { BillDetailPanel } from './components/BillDetailPanel';
import { ResultsList } from './components/ResultsList';
import { SearchToolbar } from './components/SearchToolbar';
import { StatsStrip } from './components/StatsStrip';
import { api, type BillDetail, type FilterOptions, type SearchFilters, type SearchMode, type SearchResponse, type StatsResponse } from './lib/api';

function App() {
  const [mode, setMode] = useState<SearchMode>('standard');
  const [query, setQuery] = useState('Find bundled payment legislation in Georgia and Alabama');
  const [filters, setFilters] = useState<SearchFilters>({ sort: 'relevance', limit: 8, topic: '' });
  const [options, setOptions] = useState<FilterOptions | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [selectedBillId, setSelectedBillId] = useState<string | null>(null);
  const [detail, setDetail] = useState<BillDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([api.getFilters(), api.getStats()])
      .then(([filterOptions, statsResponse]) => {
        setOptions(filterOptions);
        setStats(statsResponse);
      })
      .catch(() => {
        setError('Unable to load the backend. Start the Clause API on port 8001.');
      });
  }, []);

  async function runSearch(nextMode: SearchMode = mode) {
    setLoading(true);
    setError(null);
    try {
      const searchResponse = await api.search(nextMode, query, filters);
      setResponse(searchResponse);
      const firstBillId = searchResponse.items[0]?.bill_id ?? null;
      setSelectedBillId(firstBillId);
      if (firstBillId) {
        setDetail(await api.getBill(firstBillId));
      } else {
        setDetail(null);
      }
    } catch {
      setError('Search request failed. Check that the backend is running and the database initialized correctly.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void runSearch(mode);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSelectBill(billId: string) {
    setSelectedBillId(billId);
    try {
      setDetail(await api.getBill(billId));
    } catch {
      setError('Failed to load the selected bill.');
    }
  }

  function handleFilterChange(key: keyof SearchFilters, value: string) {
    setFilters((current) => ({
      ...current,
      [key]: value || undefined,
    }));
  }

  return (
    <AppShell
      sidebar={null}
      main={(
        <div className="workspace">
          <header className="page-header">
            <div>
              <div className="page-kicker">Bills</div>
              <h1>Bill Lookup</h1>
              <p>Search, compare, and inspect legislative records with a standard retrieval mode and a Gemini-ready agentic mode.</p>
            </div>
          </header>

          <SearchToolbar
            mode={mode}
            query={query}
            filters={filters}
            options={options}
            loading={loading}
            onModeChange={(nextMode) => {
              setMode(nextMode);
              void runSearch(nextMode);
            }}
            onQueryChange={setQuery}
            onFilterChange={handleFilterChange}
            onSearch={() => void runSearch(mode)}
          />

          <StatsStrip stats={stats} />
          {error ? <div className="error-banner">{error}</div> : null}
          <ResultsList response={response} selectedBillId={selectedBillId} onSelect={(billId) => void handleSelectBill(billId)} />
        </div>
      )}
      detail={<BillDetailPanel detail={detail} />}
    />
  );
}

export default App;
