import type { LawDetail } from '../lib/api';

type LawDetailPanelProps = {
  detail: LawDetail | null;
};

export function LawDetailPanel({ detail }: LawDetailPanelProps) {
  if (!detail) {
    return (
      <div className="detail-panel">
        <div className="empty-state">Select a law to inspect the full statute text.</div>
      </div>
    );
  }

  return (
    <div className="detail-panel">
      <h2>{detail.citation}</h2>
      <div className="detail-subtitle">{detail.heading ?? detail.source}</div>

      <section className="detail-card">
        <div className="detail-card__label">Law context</div>
        <ul>
          <li>{detail.jurisdiction}</li>
          <li>{detail.source}</li>
          <li>{detail.hierarchy_path ?? 'No hierarchy path available'}</li>
        </ul>
      </section>

      <section className="detail-card">
        <div className="detail-card__label">Excerpt</div>
        <p>{detail.body_excerpt ?? 'No excerpt available.'}</p>
      </section>

      <section className="detail-card">
        <div className="detail-card__label">Full law text</div>
        <p>{detail.body_text}</p>
      </section>

      {detail.source_url ? (
        <section className="detail-card">
          <div className="detail-card__label">Source</div>
          <a className="detail-link" href={detail.source_url} target="_blank" rel="noreferrer">
            Open official source
          </a>
        </section>
      ) : null}
    </div>
  );
}
