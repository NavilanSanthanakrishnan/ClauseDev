import type { BillDetail } from '../lib/api';

type BillDetailPanelProps = {
  detail: BillDetail | null;
};

export function BillDetailPanel({ detail }: BillDetailPanelProps) {
  if (!detail) {
    return (
      <div className="detail-panel">
        <div className="empty-state">Select a bill to inspect the full record.</div>
      </div>
    );
  }

  return (
    <div className="detail-panel">
      <h2>{detail.identifier}</h2>
      <div className="detail-subtitle">{detail.title}</div>

      <section className="detail-card">
        <div className="detail-card__label">Bill context</div>
        <ul>
          <li>{detail.jurisdiction}</li>
          <li>{detail.session_name}</li>
          <li>{detail.committee}</li>
          <li>{detail.sponsor}</li>
          <li>{detail.outcome}</li>
        </ul>
      </section>

      <section className="detail-card">
        <div className="detail-card__label">Summary</div>
        <p>{detail.summary}</p>
      </section>

      <section className="detail-card">
        <div className="detail-card__label">Full bill note</div>
        <p>{detail.full_text}</p>
      </section>

      <section className="detail-card">
        <div className="detail-card__label">Topics</div>
        <div className="tag-row">
          {detail.topics.map((topic) => (
            <span key={topic} className="tag">{topic}</span>
          ))}
        </div>
      </section>
    </div>
  );
}

