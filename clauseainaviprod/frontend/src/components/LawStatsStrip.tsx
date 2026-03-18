import type { LawStatsResponse } from '../lib/api';

type LawStatsStripProps = {
  stats: LawStatsResponse | null;
};

export function LawStatsStrip({ stats }: LawStatsStripProps) {
  const cards = [
    { label: 'Laws Indexed', value: stats ? stats.total_laws.toLocaleString() : '—' },
    { label: 'California Code', value: stats ? stats.california_laws.toLocaleString() : '—' },
    { label: 'U.S. Code', value: stats ? stats.federal_laws.toLocaleString() : '—' },
    { label: 'Coverage', value: 'Expandable by state' },
  ];

  return (
    <section className="stats-grid">
      {cards.map((card) => (
        <article key={card.label} className="stat-card">
          <div className="stat-card__label">{card.label}</div>
          <div className="stat-card__value">{card.value}</div>
        </article>
      ))}
    </section>
  );
}
