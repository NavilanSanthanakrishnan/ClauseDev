import type { LawListItem, LawSearchResponse } from '../lib/api';

type LawResultsListProps = {
  response: LawSearchResponse | null;
  selectedDocumentId: string | null;
  onSelect: (documentId: string) => void;
};

export function LawResultsList({ response, selectedDocumentId, onSelect }: LawResultsListProps) {
  const items = response?.items ?? [];

  return (
    <section className="results-layout">
      <div className="results-list">
        <div className="section-header">
          <div>
            <h2>Relevant Laws</h2>
            <p>{items.length} result{items.length === 1 ? '' : 's'} surfaced by the current legal retrieval profile.</p>
          </div>
          <div className="badge">{response?.mode === 'agentic' ? 'Agentic rerank' : 'Indexed law search'}</div>
        </div>

        {response ? (
          <div className="explanation-banner">
            <strong>{response.mode === 'agentic' ? 'Agentic plan' : 'Standard plan'}:</strong> {response.explanation}
          </div>
        ) : null}

        {items.map((law: LawListItem) => (
          <button
            key={law.document_id}
            type="button"
            className={law.document_id === selectedDocumentId ? 'bill-card bill-card--active' : 'bill-card'}
            onClick={() => onSelect(law.document_id)}
          >
            <div className="bill-card__meta">
              <span className="pill pill--strong">{law.citation}</span>
              <span className="pill">{law.jurisdiction}</span>
              <span className="pill">{law.source}</span>
              <span className="pill">Score {law.relevance_score}</span>
            </div>
            <h3>{law.heading ?? law.citation}</h3>
            <p>{law.body_excerpt ?? law.hierarchy_path ?? 'No excerpt available.'}</p>
            {law.hierarchy_path ? <div className="detail-inline-path">{law.hierarchy_path}</div> : null}
            <ul className="reason-list">
              {law.matched_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </button>
        ))}

        {response && items.length === 0 ? (
          <div className="empty-state">No laws matched the current search profile. Try a broader legal concept or switch to agentic search.</div>
        ) : null}
      </div>
    </section>
  );
}
