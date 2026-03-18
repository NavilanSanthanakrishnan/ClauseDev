import { Search } from 'lucide-react';

import type { FilterOptions, SearchFilters, SearchMode } from '../lib/api';

type SearchToolbarProps = {
  mode: SearchMode;
  query: string;
  filters: SearchFilters;
  options: FilterOptions | null;
  loading: boolean;
  onModeChange: (mode: SearchMode) => void;
  onQueryChange: (value: string) => void;
  onFilterChange: (key: keyof SearchFilters, value: string) => void;
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

export function SearchToolbar({
  mode,
  query,
  filters,
  options,
  loading,
  onModeChange,
  onQueryChange,
  onFilterChange,
  onSearch,
}: SearchToolbarProps) {
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
                ? 'Search bills, bill numbers, citations, sponsors, or policy intent...'
                : 'Describe the policy pattern, conflict, or bill family you want the agent to find...'
            }
          />
        </div>
        <button type="button" className="button button--primary" onClick={onSearch} disabled={loading}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      <div className="filter-grid">
        {renderSelect('Jurisdiction', filters.jurisdiction, options?.jurisdictions ?? [], (value) => onFilterChange('jurisdiction', value))}
        {renderSelect('Session', filters.session, options?.sessions ?? [], (value) => onFilterChange('session', value))}
        {renderSelect('Status', filters.status, options?.statuses ?? [], (value) => onFilterChange('status', value))}
        {renderSelect('Topic', filters.topic, options?.topics ?? [], (value) => onFilterChange('topic', value))}
        {renderSelect('Outcome', filters.outcome, options?.outcomes ?? [], (value) => onFilterChange('outcome', value))}
        {renderSelect('Sort', filters.sort, ['relevance', 'recent'], (value) => onFilterChange('sort', value))}
      </div>
    </section>
  );
}

