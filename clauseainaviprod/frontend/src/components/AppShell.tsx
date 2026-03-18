import {
  BookCopy,
  FileSearch,
  LogOut,
  Scale,
  Sparkles,
} from 'lucide-react';
import type { ReactNode } from 'react';

import type { RouteKey, User } from '../lib/api';

type AppShellProps = {
  activeRoute: RouteKey;
  onNavigate: (route: RouteKey) => void;
  user: User | null;
  authEnabled: boolean;
  onLogout: () => void;
  main: ReactNode;
  detail: ReactNode;
  detailTitle?: string;
};

type NavItem = {
  key: RouteKey;
  label: string;
  icon: typeof BookCopy;
  caption: string;
};

const navItems: NavItem[] = [
  { key: 'home', label: 'Bills', icon: BookCopy, caption: 'Drafts and workspaces' },
  { key: 'bill-lookup', label: 'Bill Lookup', icon: FileSearch, caption: 'Research peer legislation' },
  { key: 'law-lookup', label: 'Law Lookup', icon: Scale, caption: 'Trace governing law' },
];

function isActive(activeRoute: RouteKey, itemKey: RouteKey) {
  if (activeRoute === 'workspace' && itemKey === 'home') {
    return true;
  }
  return activeRoute === itemKey;
}

export function AppShell({
  activeRoute,
  onNavigate,
  user,
  authEnabled,
  onLogout,
  main,
  detail,
  detailTitle = 'Selected record',
}: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="app-shell__nav">
        <div>
          <div className="brand-lockup">
            <div className="brand-mark">C</div>
            <div>
              <div className="brand-title">Clause</div>
              <div className="brand-subtitle">Legislative drafting system</div>
            </div>
          </div>

          <nav className="nav-list">
            {navItems.map((item) => {
              const Icon = item.icon;

              return (
                <button
                  key={item.key}
                  type="button"
                  className={isActive(activeRoute, item.key) ? 'nav-item nav-item--active' : 'nav-item'}
                  onClick={() => onNavigate(item.key)}
                >
                  <Icon size={16} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        <div className="nav-footer">
          <div className="nav-footer__section">
            <div className="nav-footer__title">System</div>
            <div className="nav-footer__card">
              <Sparkles size={16} />
              <span>Hybrid search + Gemini agent</span>
            </div>
          </div>

          <div className="nav-footer__section">
            <div className="nav-footer__title">{authEnabled ? 'Signed in' : 'Access mode'}</div>
            <div className="nav-footer__user">
              <div>
                <strong>{user?.display_name ?? 'Demo user'}</strong>
                <span>{user?.email ?? 'Auth disabled'}</span>
              </div>
              {authEnabled ? (
                <button type="button" className="nav-footer__logout" onClick={onLogout} aria-label="Sign out">
                  <LogOut size={16} />
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </aside>

      <main className="app-shell__main">{main}</main>

      <aside className="app-shell__detail">
        <div className="detail-header">{detailTitle}</div>
        {detail}
      </aside>
    </div>
  );
}
