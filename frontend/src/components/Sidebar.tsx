import {
  FileSearch,
  FolderOpen,
  LogOut,
  MessageSquareText,
  Scale,
  Settings,
  Square,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';

import { useAuth } from '../lib/auth-context';

const navItems = [
  {
    to: '/bills',
    label: 'Your Bills',
    description: 'Create a workspace or resume a draft.',
    icon: FolderOpen,
  },
  {
    to: '/bills/database',
    label: 'Bills Database',
    description: 'Search precedent and inspect prior bills.',
    icon: FileSearch,
  },
  {
    to: '/laws/database',
    label: 'Laws Database',
    description: 'Search statutes and exact legal text.',
    icon: Scale,
  },
  {
    to: '/chat',
    label: 'Agentic Chatbot',
    description: 'Run saved research threads and follow-ups.',
    icon: MessageSquareText,
  },
];

export function Sidebar() {
  const { logout, user } = useAuth();
  const [collapsed, setCollapsed] = useState(() => window.localStorage.getItem('clauseai.sidebar.collapsed') === 'true');

  useEffect(() => {
    window.localStorage.setItem('clauseai.sidebar.collapsed', collapsed ? 'true' : 'false');
  }, [collapsed]);

  return (
    <aside className={`sidebar-shell${collapsed ? ' collapsed' : ''}`}>
      <div className="nav-sidebar">
        <button type="button" className="brand-block" onClick={() => setCollapsed((value) => !value)}>
          <div className="brand-mark">
            <Square size={18} />
          </div>
          {!collapsed ? (
            <div>
              <div className="brand-kicker">ClauseAI</div>
              <div className="brand-title">Bring your bill.</div>
              <div className="brand-subtitle">We bring you to Congress.</div>
            </div>
          ) : null}
        </button>

        <nav className="primary-nav" aria-label="Primary">
          {navItems.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-card${isActive ? ' active' : ''}`}>
                <div className="nav-icon">
                  <Icon size={18} />
                </div>
                {!collapsed ? (
                  <div>
                    <div className="nav-label">{item.label}</div>
                    <div className="nav-description">{item.description}</div>
                  </div>
                ) : null}
              </NavLink>
            );
          })}
        </nav>

        <div className="user-card">
          {!collapsed ? (
            <>
              <div className="brand-kicker">Signed in</div>
              <div className="user-name">{user?.display_name ?? 'ClauseAI user'}</div>
              <div className="user-email">{user?.email}</div>
            </>
          ) : null}
          <div className="sidebar-footer-actions">
            <NavLink to="/settings" className={({ isActive }) => `sidebar-inline-action${isActive ? ' active' : ''}`}>
              <Settings size={16} />
              {!collapsed ? <span>Settings</span> : null}
            </NavLink>
            <button type="button" className="sidebar-inline-action" onClick={() => logout()}>
              <LogOut size={16} />
              {!collapsed ? <span>Logout</span> : null}
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}
