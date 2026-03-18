import { ArrowLeft, UserPlus } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { useAuth } from '../lib/auth-context';
import { useDocumentTitle } from '../lib/useDocumentTitle';

const workflowStages = [
  {
    step: '01',
    title: 'Upload and inspect',
    detail: 'Import the bill, check extraction quality, and correct metadata before any analysis starts.',
  },
  {
    step: '02',
    title: 'Review saved analysis',
    detail: 'Read similar-bill, legal, and stakeholder reports as drafting guidance, not pre-applied edits.',
  },
  {
    step: '03',
    title: 'Approve draft diffs',
    detail: 'Finish in the Draft Editor where Codex proposes bill changes one at a time for approval.',
  },
];

export function SignupPage() {
  useDocumentTitle('Create Account');

  const navigate = useNavigate();
  const { signup } = useAuth();
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await signup(email, password, displayName);
      navigate('/bills', { replace: true });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to create the account.');
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
          <div className="page-eyebrow">Create account</div>
          <h1 className="page-title">Start a new drafting workspace</h1>
          <p className="page-description">Create an account and move straight into your bills workspace.</p>

          <form className="field-stack" onSubmit={handleSubmit}>
            <label className="field">
              <span className="field-label">Your name</span>
              <input
                aria-label="Display name"
                autoComplete="name"
                placeholder="e.g. Maya Johnson"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field-label">Email</span>
              <input
                aria-label="Email"
                autoComplete="email"
                placeholder="e.g. policyteam@city.gov"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label className="field">
              <span className="field-label">Password</span>
              <input
                aria-label="Password"
                autoComplete="new-password"
                placeholder="Create a secure password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            {error ? <div className="form-error">{error}</div> : null}
            <button type="submit" className="button button-primary" disabled={isSubmitting}>
              <UserPlus size={16} />
              {isSubmitting ? 'Creating account...' : 'Create account'}
            </button>
          </form>

          <p className="inline-note">
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </section>

        <aside className="auth-aside">
          <div className="auth-stage-shell">
            <div className="page-eyebrow">Workflow</div>
            <div className="auth-stage-list">
              {workflowStages.map((item) => (
                <article key={item.step} className="auth-stage-card">
                  <div className="auth-stage-step">{item.step}</div>
                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.detail}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>

          <div className="auth-summary-card">
            <div className="page-eyebrow">Drafting standard</div>
            <h2 className="auth-summary-title">Analysis stays separate from editing.</h2>
            <p className="page-description">
              Similar-bill, legal, and stakeholder stages save clean reports plus general drafting guidance.
              The actual bill language only changes in the final editor, with approvals and version history.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
