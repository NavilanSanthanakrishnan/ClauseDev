import { useQuery } from '@tanstack/react-query';
import { Scale, Search } from 'lucide-react';
import { useState } from 'react';

import { EmptyState } from '../components/EmptyState';
import { NextStepCard } from '../components/NextStepCard';
import { PageHeader } from '../components/PageHeader';
import { SectionFrame } from '../components/SectionFrame';
import { StatusBadge } from '../components/StatusBadge';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import { useDocumentTitle } from '../lib/useDocumentTitle';

const jurisdictionOptions = [
  { value: '', label: 'All jurisdictions' },
  { value: 'California', label: 'California' },
  { value: 'United States', label: 'United States' },
];

export function LawsDatabasePage() {
  useDocumentTitle('Laws Library');

  const { accessToken } = useAuth();
  const [searchInput, setSearchInput] = useState('labor code');
  const [query, setQuery] = useState('labor code');
  const [jurisdiction, setJurisdiction] = useState('');
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);

  const searchQuery = useQuery({
    queryKey: ['reference-laws', query, jurisdiction],
    queryFn: () => api.searchLaws(accessToken!, query, { jurisdiction }),
    enabled: Boolean(accessToken && query.trim()),
  });

  const statusQuery = useQuery({
    queryKey: ['reference-status'],
    queryFn: () => api.referenceStatus(accessToken!),
    enabled: Boolean(accessToken),
  });

  const activeDocumentId = searchQuery.data?.items.some((item) => item.document_id === selectedDocumentId)
    ? selectedDocumentId
    : (searchQuery.data?.items[0]?.document_id ?? null);

  const detailQuery = useQuery({
    queryKey: ['law-detail', activeDocumentId],
    queryFn: () => api.getLawDetail(accessToken!, activeDocumentId!),
    enabled: Boolean(accessToken && activeDocumentId),
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Laws library"
        title="Search statutes and read the exact legal text."
        description="Use this page when you want the law itself. Search, pick a result, and inspect the hierarchy and body text."
        badges={
          <>
            <StatusBadge tone="info">{`${searchQuery.data?.items.length ?? 0} matches`}</StatusBadge>
            {statusQuery.data?.law_count ? <StatusBadge tone="neutral">{`${statusQuery.data.law_count.toLocaleString()} laws loaded`}</StatusBadge> : null}
          </>
        }
      />

      <SectionFrame
        eyebrow="Search"
        title="Find the law text"
        description="Start broad, then narrow to a jurisdiction if you need to."
        icon={Search}
      >
        {statusQuery.data && !statusQuery.data.laws_ready ? (
          <div className="inline-note">Laws are still loading into the reference database. Search will improve when the build finishes.</div>
        ) : null}
        <form
          className="search-form"
          onSubmit={(event) => {
            event.preventDefault();
            setQuery(searchInput.trim());
          }}
        >
          <div className="search-primary-row">
            <input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="e.g. labor code retaliation" />
            <button type="submit" className="button button-primary">
              <Search size={16} />
              Search laws
            </button>
          </div>
          <div className="search-filter-row">
            <label className="field">
              <span className="field-label">Jurisdiction</span>
              <select value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)}>
                {jurisdictionOptions.map((option) => (
                  <option key={option.label} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </form>
      </SectionFrame>

      <div className="page-grid results-layout">
        <SectionFrame
          eyebrow="Results"
          title="Pick a law from the list"
          description="The selected law opens on the right with the hierarchy and exact text."
          icon={Scale}
        >
          <div className="result-list">
            {searchQuery.isLoading ? <div className="loading-line">Searching laws...</div> : null}
            {searchQuery.data?.items.map((item) => (
              <button
                key={item.document_id}
                type="button"
                className={`result-row${activeDocumentId === item.document_id ? ' active' : ''}`}
                onClick={() => setSelectedDocumentId(item.document_id)}
              >
                <div className="result-row-top">
                  <StatusBadge tone="info">{item.jurisdiction ?? 'jurisdiction'}</StatusBadge>
                </div>
                <strong>{item.citation ?? 'Unknown citation'}</strong>
                <p>{item.heading ?? item.hierarchy_path ?? 'No heading available.'}</p>
                <p>{item.body_excerpt ?? 'No body excerpt available.'}</p>
              </button>
            ))}
            {!searchQuery.isLoading && !searchQuery.data?.items.length ? (
              <EmptyState
                icon={Scale}
                title="No laws found"
                description="Try a broader legal term or change the jurisdiction."
              />
            ) : null}
          </div>
        </SectionFrame>

        <SectionFrame
          eyebrow="Law detail"
          title="Read the selected law"
          description="This is the exact legal text available to the conflict analysis stage."
          icon={Scale}
        >
          {detailQuery.data ? (
            <div className="detail-stack">
              <div className="detail-header">
                <div className="detail-badges">
                  <StatusBadge tone="info">{detailQuery.data.jurisdiction ?? 'jurisdiction'}</StatusBadge>
                  {detailQuery.data.source_url ? (
                    <a className="button button-secondary" href={detailQuery.data.source_url} target="_blank" rel="noreferrer">
                      Source
                    </a>
                  ) : null}
                </div>
                <h3 className="detail-title">{detailQuery.data.citation ?? 'Unknown citation'}</h3>
                <p className="detail-meta">{detailQuery.data.heading ?? detailQuery.data.hierarchy_path ?? 'No heading available.'}</p>
              </div>
              <div className="reading-pane compact">{detailQuery.data.hierarchy_path ?? 'No hierarchy path available.'}</div>
              <div className="reading-pane">{detailQuery.data.body_text ?? 'No body text available.'}</div>
            </div>
          ) : (
            <EmptyState
              icon={Scale}
              title="Choose a law"
              description="Pick any result from the left to read the exact text here."
            />
          )}
          <NextStepCard
            to="/chat"
            title="Next Page (Open Research Chat)"
            description="Ask follow-up questions after you inspect the statute text."
            icon={Search}
          />
        </SectionFrame>
      </div>
    </div>
  );
}
