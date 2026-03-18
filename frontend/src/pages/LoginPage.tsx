import { ArrowLeft, LogIn } from 'lucide-react';
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../lib/auth-context';
import { useDocumentTitle } from '../lib/useDocumentTitle';

const signInHighlights = [
  'Open the last saved workflow page for each bill.',
  'Review the saved reports before reopening Draft Editor.',
  'Resume the Codex session only when you want fresh proposed edits.',
];

export function LoginPage() {
  useDocumentTitle('Sign In');

  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login(email, password);
      navigate((location.state as { from?: string } | null)?.from ?? '/bills', { replace: true });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to sign in.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="public-shell">
      <div className="auth-layout auth-layout-dark">
        <section className="auth-panel">
          <Link to="/" className="button button-ghost">
            <ArrowLeft size={16} />
            Back
          </Link>
          <div className="auth-mark">ClauseAI</div>
          <div className="page-eyebrow">Sign in</div>
          <h1 className="page-title">Sign in to continue</h1>
          <p className="page-description">Open your saved bills, reports, versions, and editor session.</p>

          <form className="field-stack" onSubmit={handleSubmit}>
            <label className="field">
              <span className="field-label">Email</span>
              <input
                aria-label="Email"
                autoComplete="email"
                placeholder="e.g. analyst@assembly.ca.gov"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field-label">Password</span>
              <input
                aria-label="Password"
                autoComplete="current-password"
                placeholder="Enter your password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {error ? <div className="form-error">{error}</div> : null}
            <button type="submit" className="button button-primary" disabled={isSubmitting}>
              <LogIn size={16} />
              {isSubmitting ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          <p className="inline-note">
            Need an account? <Link to="/signup">Create one</Link>
          </p>
        </section>

        <aside className="auth-aside">
          <div className="auth-summary-card">
            <div className="page-eyebrow">After login</div>
            <h2 className="auth-summary-title">Resume the exact drafting state you left.</h2>
            <p className="page-description">
              ClauseAI keeps the workflow page, reports, guidance, versions, and editor state attached to each bill workspace.
            </p>
            <div className="simple-list">
              {signInHighlights.map((item) => (
                <div key={item} className="simple-list-row">
                  <strong>-</strong>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="auth-stage-shell">
            <div className="page-eyebrow">What stays visible</div>
            <div className="auth-tip-grid">
              <div className="auth-tip">
                <strong>Saved reports</strong>
                <p>Similar bills, legal conflicts, and stakeholder analysis remain attached to the project.</p>
              </div>
              <div className="auth-tip">
                <strong>Approval gates</strong>
                <p>Draft changes still require explicit approval before the live bill text changes.</p>
              </div>
              <div className="auth-tip">
                <strong>Version history</strong>
                <p>Each manual save and accepted AI diff creates a restore point.</p>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
