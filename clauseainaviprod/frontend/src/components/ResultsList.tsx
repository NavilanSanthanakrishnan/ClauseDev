import type { BillListItem, SearchResponse } from '../lib/api';

type ResultsListProps = {
  response: SearchResponse | null;
  selectedBillId: string | null;
  onSelect: (billId: string) => void;
};

export function ResultsList({ response, selectedBillId, onSelect }: ResultsListProps) {
  const items = response?.items ?? [];

  return (
    <section className="results-layout">
      <div className="results-list">
        <div className="section-header">
          <div>
            <h2>Relevant Bills</h2>
            <p>{items.length} result{items.length === 1 ? '' : 's'} surfaced by the current retrieval profile.</p>
          </div>
          <div className="badge">{response?.mode === 'agentic' ? 'Agentic rerank' : 'Hybrid lexical'}</div>
        </div>

        {response ? (
          <div className="explanation-banner">
            <strong>{response.mode === 'agentic' ? 'Agentic plan' : 'Standard plan'}:</strong> {response.explanation}
          </div>
        ) : null}

        {items.map((bill: BillListItem) => (
          <button
            key={bill.bill_id}
            type="button"
            className={bill.bill_id === selectedBillId ? 'bill-card bill-card--active' : 'bill-card'}
            onClick={() => onSelect(bill.bill_id)}
          >
            <div className="bill-card__meta">
              <span className="pill pill--strong">{bill.identifier}</span>
              <span className="pill">{bill.jurisdiction}</span>
              <span className="pill">{bill.status}</span>
              <span className="pill">Score {bill.relevance_score}</span>
            </div>
            <h3>{bill.title}</h3>
            <p>{bill.summary}</p>
            <div className="tag-row">
              {bill.topics.map((tag) => (
                <span key={tag} className="tag">{tag}</span>
              ))}
            </div>
            <ul className="reason-list">
              {bill.matched_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </button>
        ))}

        {response && items.length === 0 ? (
          <div className="empty-state">No bills matched the current search profile. Try relaxing the filters.</div>
        ) : null}
      </div>
    </section>
  );
}

