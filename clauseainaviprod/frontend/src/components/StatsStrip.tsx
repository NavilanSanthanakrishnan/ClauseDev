import type { StatsResponse } from '../lib/api';

type StatsStripProps = {
  stats: StatsResponse | null;
};

export function StatsStrip({ stats }: StatsStripProps) {
  const cards = [
    { label: 'Bills Indexed', value: stats ? stats.total_bills.toLocaleString() : '—' },
    { label: 'Jurisdictions', value: stats ? String(stats.jurisdictions) : '—' },
    { label: 'Active Sessions', value: stats ? String(stats.active_sessions) : '—' },
    { label: 'Top Topics', value: stats ? stats.top_topics.slice(0, 3).join(', ') : '—' },
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

