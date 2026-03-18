import { useQuery } from '@tanstack/react-query';
import { FileSearch, Search } from 'lucide-react';
import { useState } from 'react';

import { EmptyState } from '../components/EmptyState';
import { NextStepCard } from '../components/NextStepCard';
import { PageHeader } from '../components/PageHeader';
import { SectionFrame } from '../components/SectionFrame';
import { StatusBadge } from '../components/StatusBadge';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import { useDocumentTitle } from '../lib/useDocumentTitle';

const statusOptions = [
  { value: '', label: 'All bill statuses' },
  { value: 'enacted', label: 'Enacted' },
  { value: 'passed_not_enacted', label: 'Passed' },
  { value: 'failed_or_dead', label: 'Failed or dead' },
  { value: 'vetoed', label: 'Vetoed' },
];

export function BillsDatabasePage() {
  useDocumentTitle('Bills Library');

  const { accessToken } = useAuth();
  const [searchInput, setSearchInput] = useState('housing');
  const [query, setQuery] = useState('housing');
  const [status, setStatus] = useState('');
  const [stateCode, setStateCode] = useState('');
  const [selectedBillId, setSelectedBillId] = useState<string | null>(null);

  const searchQuery = useQuery({
    queryKey: ['reference-bills', query, status, stateCode],
    queryFn: () => api.searchBills(accessToken!, query, { status, stateCode }),
    enabled: Boolean(accessToken && query.trim()),
  });

  const statusQuery = useQuery({
    queryKey: ['reference-status'],
    queryFn: () => api.referenceStatus(accessToken!),
    enabled: Boolean(accessToken),
  });

  const activeBillId = searchQuery.data?.items.some((item) => item.bill_id === selectedBillId)
    ? selectedBillId
    : (searchQuery.data?.items[0]?.bill_id ?? null);

  const detailQuery = useQuery({
    queryKey: ['bill-detail', activeBillId],
    queryFn: () => api.getBillDetail(accessToken!, activeBillId!),
    enabled: Boolean(accessToken && activeBillId),
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Bills library"
        title="Search past bills and read them side by side."
        description="Use this page when you want precedent. Search, pick a bill from the list, and read the saved text on the right."
        badges={
          <>
            <StatusBadge tone="info">{`${searchQuery.data?.items.length ?? 0} results`}</StatusBadge>
            {statusQuery.data?.bill_count ? <StatusBadge tone="neutral">{`${statusQuery.data.bill_count.toLocaleString()} bills loaded`}</StatusBadge> : null}
          </>
        }
      />

      <SectionFrame
        eyebrow="Search"
        title="Find similar bills"
        description="Type a topic, press search, and narrow by status or state if needed."
        icon={Search}
      >
        {statusQuery.data && !statusQuery.data.bills_ready ? (
          <div className="inline-note">Bills are still loading into the reference database. Results will fill in when the build finishes.</div>
        ) : null}
        <form
          className="search-form"
          onSubmit={(event) => {
            event.preventDefault();
            setQuery(searchInput.trim());
          }}
        >
          <div className="search-primary-row">
            <input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="e.g. housing affordability" />
            <button type="submit" className="button button-primary">
              <Search size={16} />
              Search bills
            </button>
          </div>
          <div className="search-filter-row">
            <label className="field">
              <span className="field-label">Bill status</span>
              <select value={status} onChange={(event) => setStatus(event.target.value)}>
                {statusOptions.map((option) => (
                  <option key={option.label} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field-label">State code</span>
              <input value={stateCode} onChange={(event) => setStateCode(event.target.value)} placeholder="e.g. ca" />
            </label>
          </div>
        </form>
      </SectionFrame>

      <div className="page-grid results-layout">
        <SectionFrame
          eyebrow="Results"
          title="Pick a bill from the list"
          description="The full bill text opens on the right after you click any result."
          icon={FileSearch}
        >
          <div className="result-list">
            {searchQuery.isLoading ? <div className="loading-line">Searching bills...</div> : null}
            {searchQuery.data?.items.map((item) => (
              <button
                key={item.bill_id}
                type="button"
                className={`result-row${activeBillId === item.bill_id ? ' active' : ''}`}
                onClick={() => setSelectedBillId(item.bill_id)}
              >
                <div className="result-row-top">
                  <StatusBadge>{item.derived_status ?? 'unknown'}</StatusBadge>
                  <span className="mono-note">{item.state_code ?? 'multi'}</span>
                </div>
                <strong>{item.title ?? 'Untitled bill'}</strong>
                <p>{item.identifier} · {item.jurisdiction_name}</p>
                <p>{item.summary_text ?? 'No summary available yet.'}</p>
              </button>
            ))}
            {!searchQuery.isLoading && !searchQuery.data?.items.length ? (
              <EmptyState
                icon={FileSearch}
                title="No bills found"
                description="Try a broader search term or clear the filters."
              />
            ) : null}
          </div>
        </SectionFrame>

        <SectionFrame
          eyebrow="Bill detail"
          title="Read the selected bill"
          description="Use this as precedent. Keep the exact language visible while you compare it to your draft."
          icon={FileSearch}
        >
          {detailQuery.data ? (
            <div className="detail-stack">
              <div className="detail-header">
                <div className="detail-badges">
                  <StatusBadge>{detailQuery.data.derived_status ?? 'unknown'}</StatusBadge>
                  {detailQuery.data.session_identifier ? <StatusBadge tone="info">{detailQuery.data.session_identifier}</StatusBadge> : null}
                </div>
                <h3 className="detail-title">{detailQuery.data.title ?? 'Untitled bill'}</h3>
                <p className="detail-meta">
                  {detailQuery.data.identifier} · {detailQuery.data.jurisdiction_name} · {detailQuery.data.latest_action_date ?? 'No action date'}
                </p>
              </div>
              <div className="reading-pane compact">{detailQuery.data.summary_text ?? 'No summary available.'}</div>
              <div className="reading-pane">{detailQuery.data.full_text ?? 'Full text was not available in the trimmed corpus.'}</div>
            </div>
          ) : (
            <EmptyState
              icon={FileSearch}
              title="Choose a bill"
              description="Pick any result from the left to open its full details here."
            />
          )}
          <NextStepCard
            to="/laws/database"
            title="Next Page (Open Laws Library)"
            description="After you gather precedent, check the legal text that could conflict with your draft."
            icon={Search}
          />
        </SectionFrame>
      </div>
    </div>
  );
}
