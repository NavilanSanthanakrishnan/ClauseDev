import { ArrowRight, Scale, SearchCheck, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useDocumentTitle } from '../lib/useDocumentTitle';

const steps = [
  {
    title: 'Research before editing',
    description: 'Move from precedent to legal conflicts to stakeholder pressure in a fixed order.',
    icon: SearchCheck,
  },
  {
    title: 'Keep every step traceable',
    description: 'Reports, suggestions, approvals, and versions stay attached to the bill workspace.',
    icon: Sparkles,
  },
  {
    title: 'Finish in the editor',
    description: 'Run a live Codex drafting loop with approve or reject controls on the bill itself.',
    icon: Scale,
  },
];

const workflowPreview = [
  {
    label: '01 Upload and extract',
    detail: 'Bring in the bill, inspect the extracted text, and correct the metadata before analysis begins.',
  },
  {
    label: '02 Analyze first',
    detail: 'Run similar-bill, legal-conflict, and stakeholder passes as saved research artifacts.',
  },
  {
    label: '03 Finish in Draft Editor',
    detail: 'Codex proposes one bill diff at a time, and every applied edit requires approval.',
  },
];

export function HomePage() {
  useDocumentTitle('Home');

  return (
    <div className="public-shell">
      <section className="hero-shell hero-dark">
        <header className="hero-topbar">
          <div className="hero-brand-lockup">
            <div className="hero-logo-box" />
            <div>
              <div className="page-eyebrow">ClauseAI</div>
              <div className="hero-brand">Bring your bill. We bring you to Congress.</div>
            </div>
          </div>
          <div className="hero-actions">
            <Link to="/login" className="button button-secondary">
              Login
            </Link>
            <a href="https://calendly.com/" className="button button-primary" target="_blank" rel="noreferrer">Book a Demo</a>
          </div>
        </header>

        <div className="hero-layout">
          <section className="hero-copy-card">
            <div className="page-eyebrow">Agentic legislative drafting</div>
            <h1 className="hero-title">An agentic system that analyzes, edits, and polishes your bill based on laws, past bills, and stakeholders.</h1>
            <p className="hero-description">
              ClauseAI is built around a staged drafting workflow: upload the bill, review extraction, edit metadata,
              compare against precedent, inspect legal conflicts, understand stakeholder pressure, and then move into
              a live human-plus-agent editor with full approval and version history.
            </p>
            <div className="hero-actions">
              <Link to="/signup" className="button button-primary">
                Start a Workspace
                <ArrowRight size={16} />
              </Link>
              <Link to="/login" className="button button-secondary">
                Resume Saved Work
              </Link>
            </div>
          </section>

          <section className="hero-preview-card">
            <div className="hero-demo-frame">
              <div className="hero-demo-top">
                <span>ClauseAI Workflow</span>
                <span>Live workspace</span>
              </div>
              <div className="hero-demo-body">
                <div className="hero-demo-screen">
                  {workflowPreview.map((item) => (
                    <article key={item.label} className="hero-preview-stage">
                      <div className="hero-preview-label">{item.label}</div>
                      <p>{item.detail}</p>
                    </article>
                  ))}
                  <div className="hero-demo-panel">
                    <div className="hero-demo-panel-title">Approval-gated editor</div>
                    <div className="hero-demo-panel-copy">Saved reports stay visible while Codex proposes the next draft diff.</div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </section>

      <section className="landing-grid landing-grid-dark">
        {steps.map((step) => {
          const Icon = step.icon;

          return (
            <article key={step.title} className="landing-card">
              <div className="section-icon">
                <Icon size={18} />
              </div>
              <h2 className="section-title">{step.title}</h2>
              <p className="section-description">{step.description}</p>
            </article>
          );
        })}
      </section>
    </div>
  );
}
