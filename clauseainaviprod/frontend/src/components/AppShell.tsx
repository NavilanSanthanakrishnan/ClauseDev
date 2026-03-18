import {
  BookOpenText,
  Database,
  FileSearch,
  Search,
  Sparkles,
} from 'lucide-react';
import type { ReactNode } from 'react';

type AppShellProps = {
  sidebar: ReactNode;
  main: ReactNode;
  detail: ReactNode;
};

const navItems = [
  { label: 'Bills', icon: Database, active: true },
  { label: 'Search Lab', icon: Search, active: false },
  { label: 'Briefing', icon: BookOpenText, active: false },
  { label: 'Artifacts', icon: FileSearch, active: false },
];

export function AppShell({ sidebar, main, detail }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="app-shell__nav">
        <div>
          <div className="brand-lockup">
            <div className="brand-mark">C</div>
            <div>
              <div className="brand-title">Clause</div>
              <div className="brand-subtitle">Legislative desktop</div>
            </div>
          </div>

          <nav className="nav-list">
            {navItems.map((item) => {
              const Icon = item.icon;

              return (
                <button
                  key={item.label}
                  type="button"
                  className={item.active ? 'nav-item nav-item--active' : 'nav-item'}
                >
                  <Icon size={16} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        <div className="nav-footer">
          <div className="nav-footer__title">Mode</div>
          <div className="nav-footer__card">
            <Sparkles size={16} />
            <span>Bills only</span>
          </div>
        </div>
      </aside>

      <main className="app-shell__main">{main}</main>
      <aside className="app-shell__detail">
        <div className="detail-header">Selected Bill</div>
        {detail}
      </aside>
      <div className="app-shell__mobile-sidebar">{sidebar}</div>
    </div>
  );
}

