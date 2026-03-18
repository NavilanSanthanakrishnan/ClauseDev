import {
  BookCopy,
  FileSearch,
  Inbox,
  PenLine,
  Scale,
  Sparkles,
} from 'lucide-react';
import type { FormEvent } from 'react';

type LoginScreenProps = {
  email: string;
  password: string;
  loading: boolean;
  error: string | null;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: () => void;
};

const navItems = [
  { label: 'Bills', icon: BookCopy },
  { label: 'Bill Lookup', icon: FileSearch },
  { label: 'Law Lookup', icon: Scale },
  { label: 'Workspace Agent', icon: Sparkles },
  { label: 'Markup', icon: PenLine },
  { label: 'Inbox', icon: Inbox },
];

export function LoginScreen({
  email,
  password,
  loading,
  error,
  onEmailChange,
  onPasswordChange,
  onSubmit,
}: LoginScreenProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <div className="login-shell">
      <aside className="login-shell__nav">
        <div className="brand-lockup">
          <div className="brand-mark">C</div>
          <div>
            <div className="brand-title">Clause</div>
            <div className="brand-subtitle">Legislative drafting system</div>
          </div>
        </div>

        <nav className="nav-list">
          {navItems.map((item, index) => {
            const Icon = item.icon;

            return (
              <div key={item.label} className={index === 0 ? 'nav-item nav-item--active nav-item--static' : 'nav-item nav-item--static'}>
                <Icon size={16} />
                <span>{item.label}</span>
              </div>
            );
          })}
        </nav>

        <div className="login-shell__footer">Sign in to open search, drafting, and agent workflows.</div>
      </aside>

      <main className="login-shell__main">
        <form className="login-card" onSubmit={handleSubmit}>
          <div className="login-card__eyebrow">Clause</div>
          <h1>Welcome back</h1>
          <p>Sign in to continue into the drafting workspace.</p>

          <label className="form-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => onEmailChange(event.target.value)}
              placeholder="you@team.com"
              autoComplete="username"
            />
          </label>

          <label className="form-field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password"
            />
          </label>

          {error ? <div className="error-banner">{error}</div> : null}

          <button type="submit" className="button button--light button--full" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </main>
    </div>
  );
}
