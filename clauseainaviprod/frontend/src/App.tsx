import { useEffect, useState } from 'react';

import { AppShell } from './components/AppShell';
import { BillDetailPanel } from './components/BillDetailPanel';
import { LawDetailPanel } from './components/LawDetailPanel';
import { LawResultsList } from './components/LawResultsList';
import { LawSearchToolbar } from './components/LawSearchToolbar';
import { LawStatsStrip } from './components/LawStatsStrip';
import { ResultsList } from './components/ResultsList';
import { SearchToolbar } from './components/SearchToolbar';
import { StatsStrip } from './components/StatsStrip';
import {
  api,
  type BillDetail,
  type BillFilterOptions,
  type BillSearchFilters,
  type LawDetail,
  type LawFilterOptions,
  type LawSearchFilters,
  type LawSearchResponse,
  type LawStatsResponse,
  type SearchMode,
  type SearchResponse,
  type StatsResponse,
  type WorkspaceMode,
} from './lib/api';

function App() {
  const [workspace, setWorkspace] = useState<WorkspaceMode>(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('workspace') === 'laws' ? 'laws' : 'bills';
  });
  const [billMode, setBillMode] = useState<SearchMode>('standard');
  const [billQuery, setBillQuery] = useState('Find bundled payment legislation in Georgia and Alabama');
  const [billFilters, setBillFilters] = useState<BillSearchFilters>({ sort: 'relevance', limit: 8, topic: '' });
  const [billOptions, setBillOptions] = useState<BillFilterOptions | null>(null);
  const [billStats, setBillStats] = useState<StatsResponse | null>(null);
  const [billResponse, setBillResponse] = useState<SearchResponse | null>(null);
  const [selectedBillId, setSelectedBillId] = useState<string | null>(null);
  const [billDetail, setBillDetail] = useState<BillDetail | null>(null);
  const [lawMode, setLawMode] = useState<SearchMode>('standard');
  const [lawQuery, setLawQuery] = useState('Find wildfire risk laws');
  const [lawFilters, setLawFilters] = useState<LawSearchFilters>({ sort: 'relevance', limit: 8 });
  const [lawOptions, setLawOptions] = useState<LawFilterOptions | null>(null);
  const [lawStats, setLawStats] = useState<LawStatsResponse | null>(null);
  const [lawResponse, setLawResponse] = useState<LawSearchResponse | null>(null);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [lawDetail, setLawDetail] = useState<LawDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateWorkspace(nextWorkspace: WorkspaceMode) {
    setWorkspace(nextWorkspace);
    const url = new URL(window.location.href);
    if (nextWorkspace === 'laws') {
      url.searchParams.set('workspace', 'laws');
    } else {
      url.searchParams.delete('workspace');
    }
    window.history.replaceState({}, '', url);
  }

  useEffect(() => {
    void Promise.all([api.getFilters(), api.getStats(), api.getLawFilters(), api.getLawStats()])
      .then(([nextBillOptions, nextBillStats, nextLawOptions, nextLawStats]) => {
        setBillOptions(nextBillOptions);
        setBillStats(nextBillStats);
        setLawOptions(nextLawOptions);
        setLawStats(nextLawStats);
      })
      .catch(() => {
        setError('Unable to load the backend. Start the Clause API on port 8001.');
      });
  }, []);

  async function runBillSearch(nextMode: SearchMode = billMode) {
    setLoading(true);
    setError(null);
    try {
      const searchResponse = await api.search(nextMode, billQuery, billFilters);
      setBillResponse(searchResponse);
      const firstBillId = searchResponse.items[0]?.bill_id ?? null;
      setSelectedBillId(firstBillId);
      if (firstBillId) {
        setBillDetail(await api.getBill(firstBillId));
      } else {
        setBillDetail(null);
      }
    } catch {
      setError('Search request failed. Check that the backend is running and the database initialized correctly.');
    } finally {
      setLoading(false);
    }
  }

  async function runLawSearch(nextMode: SearchMode = lawMode) {
    setLoading(true);
    setError(null);
    try {
      const searchResponse = await api.searchLaws(nextMode, lawQuery, lawFilters);
      setLawResponse(searchResponse);
      const firstDocumentId = searchResponse.items[0]?.document_id ?? null;
      setSelectedDocumentId(firstDocumentId);
      if (firstDocumentId) {
        setLawDetail(await api.getLaw(firstDocumentId));
      } else {
        setLawDetail(null);
      }
    } catch {
      setError('Law search failed. Check that the external law databases are reachable.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (workspace === 'laws') {
      void runLawSearch(lawMode);
      return;
    }
    void runBillSearch(billMode);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSelectBill(billId: string) {
    setSelectedBillId(billId);
    try {
      setBillDetail(await api.getBill(billId));
    } catch {
      setError('Failed to load the selected bill.');
    }
  }

  async function handleSelectLaw(documentId: string) {
    setSelectedDocumentId(documentId);
    try {
      setLawDetail(await api.getLaw(documentId));
    } catch {
      setError('Failed to load the selected law.');
    }
  }

  function handleBillFilterChange(key: keyof BillSearchFilters, value: string) {
    setBillFilters((current) => ({
      ...current,
      [key]: value || undefined,
    }));
  }

  function handleLawFilterChange(key: keyof LawSearchFilters, value: string) {
    setLawFilters((current) => ({
      ...current,
      [key]: value || undefined,
    }));
  }

  return (
    <AppShell
      sidebar={null}
      detailTitle={workspace === 'bills' ? 'Selected Bill' : 'Selected Law'}
      main={(
        <div className="workspace">
          <header className="page-header">
            <div>
              <div className="page-kicker">{workspace === 'bills' ? 'Bills' : 'Laws'}</div>
              <h1>{workspace === 'bills' ? 'Bill Lookup' : 'Law Lookup'}</h1>
              <p>
                {workspace === 'bills'
                  ? 'Search, compare, and inspect legislative records with standard retrieval and a live Gemini-backed agentic mode.'
                  : 'Search exact statutes, inspect full text, and use an agentic legal retrieval path for conflicts, contradictions, and related laws.'}
              </p>
            </div>
            <div className="page-header__actions workspace-switch">
              <button
                type="button"
                className={workspace === 'bills' ? 'button button--primary' : 'button'}
                onClick={() => {
                  updateWorkspace('bills');
                }}
              >
                Bill Lookup
              </button>
              <button
                type="button"
                className={workspace === 'laws' ? 'button button--primary' : 'button'}
                onClick={() => {
                  updateWorkspace('laws');
                  if (!lawResponse) {
                    void runLawSearch(lawMode);
                  }
                }}
              >
                Law Lookup
              </button>
            </div>
          </header>

          {workspace === 'bills' ? (
            <>
              <SearchToolbar
                mode={billMode}
                query={billQuery}
                filters={billFilters}
                options={billOptions}
                loading={loading}
                onModeChange={(nextMode) => {
                  setBillMode(nextMode);
                  void runBillSearch(nextMode);
                }}
                onQueryChange={setBillQuery}
                onFilterChange={handleBillFilterChange}
                onSearch={() => void runBillSearch(billMode)}
              />
              <StatsStrip stats={billStats} />
            </>
          ) : (
            <>
              <LawSearchToolbar
                mode={lawMode}
                query={lawQuery}
                filters={lawFilters}
                options={lawOptions}
                loading={loading}
                onModeChange={(nextMode) => {
                  setLawMode(nextMode);
                  void runLawSearch(nextMode);
                }}
                onQueryChange={setLawQuery}
                onFilterChange={handleLawFilterChange}
                onSearch={() => void runLawSearch(lawMode)}
              />
              <LawStatsStrip stats={lawStats} />
            </>
          )}

          {error ? <div className="error-banner">{error}</div> : null}
          {workspace === 'bills' ? (
            <ResultsList response={billResponse} selectedBillId={selectedBillId} onSelect={(billId) => void handleSelectBill(billId)} />
          ) : (
            <LawResultsList response={lawResponse} selectedDocumentId={selectedDocumentId} onSelect={(documentId) => void handleSelectLaw(documentId)} />
          )}
        </div>
      )}
      detail={workspace === 'bills' ? <BillDetailPanel detail={billDetail} /> : <LawDetailPanel detail={lawDetail} />}
    />
  );
}

export default App;
