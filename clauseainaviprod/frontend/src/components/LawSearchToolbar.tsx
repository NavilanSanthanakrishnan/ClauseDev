import { Search } from 'lucide-react';

import type { LawFilterOptions, LawSearchFilters, SearchMode } from '../lib/api';

type LawSearchToolbarProps = {
  mode: SearchMode;
  query: string;
  filters: LawSearchFilters;
  options: LawFilterOptions | null;
  loading: boolean;
  onModeChange: (mode: SearchMode) => void;
  onQueryChange: (value: string) => void;
  onFilterChange: (key: keyof LawSearchFilters, value: string) => void;
  onSearch: () => void;
};

function renderSelect(
  label: string,
  value: string | undefined,
  values: string[],
  onChange: (value: string) => void,
) {
  return (
    <label className="filter-select">
      <span>{label}</span>
      <select value={value ?? ''} onChange={(event) => onChange(event.target.value)}>
        <option value="">All</option>
        {values.map((item) => (
          <option key={item} value={item}>{item}</option>
        ))}
      </select>
    </label>
  );
}

export function LawSearchToolbar({
  mode,
  query,
  filters,
  options,
  loading,
  onModeChange,
  onQueryChange,
  onFilterChange,
  onSearch,
}: LawSearchToolbarProps) {
  return (
    <section className="search-panel">
      <div className="page-header__actions">
        <button
          type="button"
          className={mode === 'standard' ? 'button button--primary' : 'button'}
          onClick={() => onModeChange('standard')}
        >
          Normal Search
        </button>
        <button
          type="button"
          className={mode === 'agentic' ? 'button button--primary' : 'button'}
          onClick={() => onModeChange('agentic')}
        >
          Agentic Search
        </button>
      </div>

      <div className="search-bar">
        <div className="search-input">
          <Search size={18} />
          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder={
              mode === 'standard'
                ? 'Search statutes, citations, legal sections, or keywords like wildfire risk laws...'
                : 'Describe the conflict, contradiction, or legal concept you want the agent to trace...'
            }
          />
        </div>
        <button type="button" className="button button--primary" onClick={onSearch} disabled={loading}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      <div className="filter-grid filter-grid--laws">
        {renderSelect('Jurisdiction', filters.jurisdiction, options?.jurisdictions ?? [], (value) => onFilterChange('jurisdiction', value))}
        {renderSelect('Source', filters.source, options?.sources ?? [], (value) => onFilterChange('source', value))}
      </div>
    </section>
  );
}
