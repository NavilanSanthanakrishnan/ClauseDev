import { Search } from 'lucide-react';
import { useMemo, useState } from 'react';

import { AppShell } from './components/AppShell';
import { mockBills } from './lib/mock-data';

const filterChips = [
  'Jurisdiction: All',
  'Session: Active',
  'Status: Any',
  'Topic: Privacy',
  'Outcome: Passed + Failed',
  'Sort: Relevance',
];

function App() {
  const [query, setQuery] = useState('Find bundled payment legislation in Georgia and Alabama');
  const [selectedId, setSelectedId] = useState(mockBills[0].id);

  const filteredBills = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return mockBills;
    }

    return mockBills.filter((bill) => {
      const haystack = [
        bill.id,
        bill.state,
        bill.title,
        bill.summary,
        bill.excerpt,
        ...bill.tags,
      ].join(' ').toLowerCase();

      return haystack.includes(normalized) || normalized.split(' ').some((token) => haystack.includes(token));
    });
  }, [query]);

  const selectedBill = filteredBills.find((bill) => bill.id === selectedId) ?? filteredBills[0] ?? mockBills[0];

  return (
    <AppShell
      sidebar={null}
      main={(
        <div className="workspace">
          <header className="page-header">
            <div>
              <div className="page-kicker">Bills</div>
              <h1>Bill Lookup</h1>
              <p>Search, compare, and inspect legislative records with a standard mode and a guided search mode.</p>
            </div>
            <div className="page-header__actions">
              <button type="button" className="button button--primary">Normal Search</button>
              <button type="button" className="button">Guided Search</button>
            </div>
          </header>

          <section className="search-panel">
            <div className="search-bar">
              <div className="search-input">
                <Search size={18} />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search bills, bill numbers, citations, sponsors, or policy intent..."
                />
              </div>
              <button type="button" className="button button--primary">Search</button>
            </div>

            <div className="chip-row">
              {filterChips.map((chip) => (
                <div key={chip} className="chip">{chip}</div>
              ))}
            </div>
          </section>

          <section className="results-layout">
            <div className="results-list">
              <div className="section-header">
                <div>
                  <h2>Relevant Bills</h2>
                  <p>{filteredBills.length} result{filteredBills.length === 1 ? '' : 's'} surfaced by the current retrieval profile.</p>
                </div>
                <div className="badge">High relevance</div>
              </div>

              {filteredBills.map((bill) => (
                <button
                  key={bill.id}
                  type="button"
                  className={bill.id === selectedBill.id ? 'bill-card bill-card--active' : 'bill-card'}
                  onClick={() => setSelectedId(bill.id)}
                >
                  <div className="bill-card__meta">
                    <span className="pill pill--strong">{bill.id}</span>
                    <span className="pill">{bill.state}</span>
                    <span className="pill">{bill.status}</span>
                  </div>
                  <h3>{bill.title}</h3>
                  <p>{bill.summary}</p>
                  <blockquote>{bill.excerpt}</blockquote>
                  <div className="tag-row">
                    {bill.tags.map((tag) => (
                      <span key={tag} className="tag">{tag}</span>
                    ))}
                  </div>
                </button>
              ))}
            </div>
          </section>
        </div>
      )}
      detail={(
        <div className="detail-panel">
          <h2>{selectedBill.id}</h2>
          <div className="detail-subtitle">{selectedBill.title}</div>

          <section className="detail-card">
            <div className="detail-card__label">Bill context</div>
            <ul>
              <li>{selectedBill.state}</li>
              <li>{selectedBill.committee}</li>
              <li>{selectedBill.sponsor}</li>
            </ul>
          </section>

          <section className="detail-card">
            <div className="detail-card__label">Why this matched</div>
            <ul>
              {selectedBill.whyMatched.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </section>

          <section className="detail-card">
            <div className="detail-card__label">Summary</div>
            <p>{selectedBill.summary}</p>
          </section>
        </div>
      )}
    />
  );
}

export default App;

