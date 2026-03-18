import { startTransition, useEffect, useMemo, useState } from 'react';

import { AppShell } from './components/AppShell';
import { BillDetailPanel } from './components/BillDetailPanel';
import { LawDetailPanel } from './components/LawDetailPanel';
import { LawResultsList } from './components/LawResultsList';
import { LawSearchToolbar } from './components/LawSearchToolbar';
import { LawStatsStrip } from './components/LawStatsStrip';
import { LoginScreen } from './components/LoginScreen';
import { ResultsList } from './components/ResultsList';
import { SearchToolbar } from './components/SearchToolbar';
import { StatsStrip } from './components/StatsStrip';
import {
  api,
  type AgentResponse,
  type BillDetail,
  type BillFilterOptions,
  type BillSearchFilters,
  type BillSearchResponse,
  type BillStats,
  type CreateProjectInput,
  type LawDetail,
  type LawFilterOptions,
  type LawSearchFilters,
  type LawSearchResponse,
  type LawStats,
  type ProjectDetail,
  type ProjectInsightEnvelope,
  type ProjectListItem,
  type RouteKey,
  type SearchMode,
  type User,
} from './lib/api';

const TOKEN_STORAGE_KEY = 'clause.token';

type ProjectDraft = {
  title: string;
  policy_goal: string;
  jurisdiction: string;
  status: string;
  stage: string;
  summary: string;
  bill_text: string;
};

function projectToDraft(project: ProjectDetail): ProjectDraft {
  return {
    title: project.title,
    policy_goal: project.policy_goal,
    jurisdiction: project.jurisdiction ?? '',
    status: project.status,
    stage: project.stage,
    summary: project.summary,
    bill_text: project.bill_text,
  };
}

function insightPayload(envelope: ProjectInsightEnvelope | undefined): Record<string, unknown> | null {
  return envelope?.payload ?? null;
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string');
}

function formatRelativeDate(value: string | undefined) {
  if (!value) {
    return 'No recent update';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}

function buildProjectFromBill(detail: BillDetail): CreateProjectInput {
  return {
    title: detail.title,
    policy_goal: detail.summary,
    jurisdiction: detail.jurisdiction,
  };
}

function App() {
  const [route, setRoute] = useState<RouteKey>('home');
  const [authEnabled, setAuthEnabled] = useState(false);
  const [authReady, setAuthReady] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authBusy, setAuthBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [billMode, setBillMode] = useState<SearchMode>('standard');
  const [billQuery, setBillQuery] = useState('Find bundled payment legislation in Georgia and Alabama');
  const [billFilters, setBillFilters] = useState<BillSearchFilters>({ sort: 'relevance', limit: 8, topic: '' });
  const [billOptions, setBillOptions] = useState<BillFilterOptions | null>(null);
  const [billStats, setBillStats] = useState<BillStats | null>(null);
  const [billResponse, setBillResponse] = useState<BillSearchResponse | null>(null);
  const [selectedBillId, setSelectedBillId] = useState<string | null>(null);
  const [billDetail, setBillDetail] = useState<BillDetail | null>(null);
  const [billLoading, setBillLoading] = useState(false);

  const [lawMode, setLawMode] = useState<SearchMode>('standard');
  const [lawQuery, setLawQuery] = useState('Which law contradicts this section about wildfire risk disclosure requirements?');
  const [lawFilters, setLawFilters] = useState<LawSearchFilters>({ sort: 'relevance', limit: 8 });
  const [lawOptions, setLawOptions] = useState<LawFilterOptions | null>(null);
  const [lawStats, setLawStats] = useState<LawStats | null>(null);
  const [lawResponse, setLawResponse] = useState<LawSearchResponse | null>(null);
  const [selectedLawId, setSelectedLawId] = useState<string | null>(null);
  const [lawDetail, setLawDetail] = useState<LawDetail | null>(null);
  const [lawLoading, setLawLoading] = useState(false);

  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [projectDetail, setProjectDetail] = useState<ProjectDetail | null>(null);
  const [projectLoading, setProjectLoading] = useState(false);
  const [workspaceBusy, setWorkspaceBusy] = useState(false);
  const [agentPrompt, setAgentPrompt] = useState('Find the main drafting risks and give me the next revision to make.');
  const [agentResult, setAgentResult] = useState<AgentResponse | null>(null);
  const [draft, setDraft] = useState<ProjectDraft | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createTitle, setCreateTitle] = useState('');
  const [createGoal, setCreateGoal] = useState('');
  const [createJurisdiction, setCreateJurisdiction] = useState('');

  const selectedProjectSummary = useMemo(
    () => projects.find((project) => project.project_id === selectedProjectId) ?? projects[0] ?? null,
    [projects, selectedProjectId],
  );

  async function loadAppData(activeToken: string | null) {
    const [nextBillOptions, nextBillStats, nextLawOptions, nextLawStats, nextProjects] = await Promise.all([
      api.getBillFilters(activeToken),
      api.getBillStats(activeToken),
      api.getLawFilters(activeToken),
      api.getLawStats(activeToken),
      api.listProjects(activeToken),
    ]);

    setBillOptions(nextBillOptions);
    setBillStats(nextBillStats);
    setLawOptions(nextLawOptions);
    setLawStats(nextLawStats);
    setProjects(nextProjects);
    setSelectedProjectId((current) => current ?? nextProjects[0]?.project_id ?? null);
  }

  async function bootstrap() {
    setError(null);
    try {
      const authConfig = await api.getAuthConfig();
      setAuthEnabled(authConfig.enabled);
      const storedToken = authConfig.enabled ? window.localStorage.getItem(TOKEN_STORAGE_KEY) : null;
      setToken(storedToken);

      if (authConfig.enabled && !storedToken) {
        setAuthReady(true);
        return;
      }

      const currentUser = await api.me(storedToken);
      setUser(currentUser);
      await loadAppData(storedToken);
    } catch (nextError) {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
      setToken(null);
      setUser(null);
      setError(nextError instanceof Error ? nextError.message : 'Unable to connect to the Clause backend.');
    } finally {
      setAuthReady(true);
    }
  }

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => {
    if (!selectedProjectId || !user) {
      return;
    }

    let cancelled = false;
    setProjectLoading(true);
    void api.getProject(selectedProjectId, token)
      .then((project) => {
        if (cancelled) {
          return;
        }
        setProjectDetail(project);
        setDraft(projectToDraft(project));
      })
      .catch((nextError) => {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : 'Failed to load the workspace.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setProjectLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedProjectId, token, user]);

  async function handleLogin() {
    setAuthBusy(true);
    setError(null);
    try {
      const response = await api.login(authEmail, authPassword);
      window.localStorage.setItem(TOKEN_STORAGE_KEY, response.token);
      setToken(response.token);
      setUser(response.user);
      await loadAppData(response.token);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Sign-in failed.');
    } finally {
      setAuthBusy(false);
    }
  }

  async function handleLogout() {
    await api.logout(token);
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);
    setAuthReady(true);
    setRoute('home');
  }

  async function runBillSearch(nextMode: SearchMode = billMode) {
    setBillLoading(true);
    setError(null);
    try {
      const response = await api.searchBills(nextMode, billQuery, billFilters, token);
      setBillResponse(response);
      const firstBillId = response.items[0]?.bill_id ?? null;
      setSelectedBillId(firstBillId);
      setBillDetail(firstBillId ? await api.getBill(firstBillId, token) : null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Bill search failed.');
    } finally {
      setBillLoading(false);
    }
  }

  async function runLawSearch(nextMode: SearchMode = lawMode) {
    setLawLoading(true);
    setError(null);
    try {
      const response = await api.searchLaws(nextMode, lawQuery, lawFilters, token);
      setLawResponse(response);
      const firstLawId = response.items[0]?.document_id ?? null;
      setSelectedLawId(firstLawId);
      setLawDetail(firstLawId ? await api.getLaw(firstLawId, token) : null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Law search failed.');
    } finally {
      setLawLoading(false);
    }
  }

  useEffect(() => {
    if (!user) {
      return;
    }
    void runBillSearch();
    void runLawSearch();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  async function handleSelectBill(billId: string) {
    setSelectedBillId(billId);
    try {
      setBillDetail(await api.getBill(billId, token));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to load the selected bill.');
    }
  }

  async function handleSelectLaw(documentId: string) {
    setSelectedLawId(documentId);
    try {
      setLawDetail(await api.getLaw(documentId, token));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to load the selected law.');
    }
  }

  async function openProject(projectId: string, nextRoute: RouteKey = 'workspace') {
    setSelectedProjectId(projectId);
    startTransition(() => {
      setRoute(nextRoute);
    });
  }

  async function refreshProjectList(preferredProjectId?: string | null) {
    const nextProjects = await api.listProjects(token);
    setProjects(nextProjects);
    if (preferredProjectId) {
      setSelectedProjectId(preferredProjectId);
      return;
    }
    setSelectedProjectId((current) => current ?? nextProjects[0]?.project_id ?? null);
  }

  async function createProject(input?: CreateProjectInput) {
    const payload = input ?? {
      title: createTitle.trim(),
      policy_goal: createGoal.trim(),
      jurisdiction: createJurisdiction.trim() || undefined,
    };
    if (!payload.title || !payload.policy_goal) {
      setError('Title and policy goal are required to create a bill workspace.');
      return;
    }

    setWorkspaceBusy(true);
    setError(null);
    try {
      const project = await api.createProject(payload, token);
      await refreshProjectList(project.project_id);
      setProjectDetail(project);
      setDraft(projectToDraft(project));
      setCreateOpen(false);
      setCreateTitle('');
      setCreateGoal('');
      setCreateJurisdiction('');
      startTransition(() => {
        setRoute('workspace');
      });
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to create the workspace.');
    } finally {
      setWorkspaceBusy(false);
    }
  }

  async function saveProject() {
    if (!selectedProjectId || !draft) {
      return;
    }
    setWorkspaceBusy(true);
    setError(null);
    try {
      const project = await api.updateProject(selectedProjectId, {
        ...draft,
        jurisdiction: draft.jurisdiction || undefined,
      }, token);
      setProjectDetail(project);
      setDraft(projectToDraft(project));
      await refreshProjectList(project.project_id);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to save the draft.');
    } finally {
      setWorkspaceBusy(false);
    }
  }

  async function refreshInsights() {
    if (!selectedProjectId) {
      return;
    }
    setWorkspaceBusy(true);
    setError(null);
    try {
      await api.refreshInsights(selectedProjectId, token);
      const project = await api.getProject(selectedProjectId, token);
      setProjectDetail(project);
      setDraft(projectToDraft(project));
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Failed to refresh workspace intelligence.');
    } finally {
      setWorkspaceBusy(false);
    }
  }

  async function sendAgentMessage() {
    if (!selectedProjectId || !agentPrompt.trim()) {
      return;
    }
    setWorkspaceBusy(true);
    setError(null);
    try {
      const response = await api.agentChat(selectedProjectId, agentPrompt.trim(), token);
      setAgentResult(response);
      setProjectDetail((current) => {
        if (!current) {
          return current;
        }
        return {
          ...current,
          messages: [...current.messages, response.message],
        };
      });
      if (response.suggested_stage || response.suggested_status) {
        setDraft((current) => current ? {
          ...current,
          stage: response.suggested_stage ?? current.stage,
          status: response.suggested_status ?? current.status,
        } : current);
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Agent request failed.');
    } finally {
      setWorkspaceBusy(false);
    }
  }

  function handleBillFilterChange(key: keyof BillSearchFilters, value: string) {
    setBillFilters((current) => ({
      ...current,
      [key]: value || undefined,
    }));
  }

  function handleLawFilterChange(key: keyof LawSearchFilters, value: string) {
    setLawFilters((current) => ({
      ...current,
      [key]: value || undefined,
    }));
  }

  function updateDraft(key: keyof ProjectDraft, value: string) {
    setDraft((current) => current ? { ...current, [key]: value } : current);
  }

  const draftingFocus = insightPayload(projectDetail?.insights.drafting_focus);
  const stakeholders = insightPayload(projectDetail?.insights.stakeholders);
  const similarBills = (insightPayload(projectDetail?.insights.similar_bills)?.items as Array<Record<string, unknown>> | undefined) ?? [];
  const conflictingLaws = (insightPayload(projectDetail?.insights.conflicting_laws)?.items as Array<Record<string, unknown>> | undefined) ?? [];
  const canUseApp = authReady && (!authEnabled || !!user);

  if (!authReady) {
    return <div className="splash-screen">Loading Clause…</div>;
  }

  if (authEnabled && !user) {
    return (
      <LoginScreen
        email={authEmail}
        password={authPassword}
        loading={authBusy}
        error={error}
        onEmailChange={setAuthEmail}
        onPasswordChange={setAuthPassword}
        onSubmit={() => {
          void handleLogin();
        }}
      />
    );
  }

  if (!canUseApp) {
    return <div className="splash-screen">Unable to start Clause.</div>;
  }

  const homeMain = (
    <div className="workspace">
      <header className="page-header">
        <div>
          <div className="page-kicker">Bills</div>
          <h1>Drafting home</h1>
          <p>
            Start a bill, reopen an active draft, or move from research into a workspace where the editor,
            similar bills, conflicting laws, stakeholders, and the agent stay in the same loop.
          </p>
        </div>
        <div className="page-header__actions">
          <button type="button" className="button button--primary" onClick={() => setCreateOpen((current) => !current)}>
            {createOpen ? 'Close new bill' : 'New bill'}
          </button>
        </div>
      </header>

      <section className="surface surface--hero">
        <div className="surface__header">
          <div>
            <h2>Workspaces</h2>
            <p>Each workspace keeps drafting and retrieval together so users do not lose context between tools.</p>
          </div>
          <div className="surface__eyebrow">{projects.length} active</div>
        </div>

        {createOpen ? (
          <div className="form-grid">
            <label className="form-field">
              <span>Bill title</span>
              <input value={createTitle} onChange={(event) => setCreateTitle(event.target.value)} placeholder="Consumer Data Broker Accountability Act" />
            </label>
            <label className="form-field">
              <span>Jurisdiction</span>
              <input value={createJurisdiction} onChange={(event) => setCreateJurisdiction(event.target.value)} placeholder="California" />
            </label>
            <label className="form-field form-field--full">
              <span>Policy goal</span>
              <textarea value={createGoal} onChange={(event) => setCreateGoal(event.target.value)} placeholder="Tighten data broker duties while keeping enforcement committee-safe." rows={3} />
            </label>
            <div className="form-actions">
              <button type="button" className="button button--primary" disabled={workspaceBusy} onClick={() => void createProject()}>
                {workspaceBusy ? 'Creating...' : 'Create workspace'}
              </button>
            </div>
          </div>
        ) : null}

        <div className="project-grid">
          {projects.map((project) => (
            <button
              key={project.project_id}
              type="button"
              className={project.project_id === selectedProjectSummary?.project_id ? 'project-card project-card--active' : 'project-card'}
              onClick={() => {
                setSelectedProjectId(project.project_id);
              }}
            >
              <div className="project-card__meta">
                <span className="pill pill--strong">{project.stage}</span>
                <span className="pill">{project.status}</span>
                {project.jurisdiction ? <span className="pill">{project.jurisdiction}</span> : null}
              </div>
              <h3>{project.title}</h3>
              <p>{project.summary || project.policy_goal}</p>
              <div className="project-card__footer">
                <span>Updated {formatRelativeDate(project.updated_at)}</span>
                <span className="project-card__link">Open workspace</span>
              </div>
            </button>
          ))}
        </div>
      </section>
    </div>
  );

  const homeDetail = selectedProjectSummary ? (
    <div className="detail-panel">
      <h2>{selectedProjectSummary.title}</h2>
      <div className="detail-subtitle">{selectedProjectSummary.policy_goal}</div>

      <section className="detail-card">
        <div className="detail-card__label">Workspace snapshot</div>
        <ul>
          <li>{selectedProjectSummary.stage}</li>
          <li>{selectedProjectSummary.status}</li>
          <li>{selectedProjectSummary.jurisdiction ?? 'Jurisdiction not set'}</li>
          <li>Updated {formatRelativeDate(selectedProjectSummary.updated_at)}</li>
        </ul>
      </section>

      <section className="detail-card">
        <div className="detail-card__label">Why this flow</div>
        <p>
          Clause keeps search, legal constraints, stakeholder pressure, and revision suggestions inside the same bill
          workspace so drafting does not become a chain of disconnected tabs.
        </p>
      </section>

      <button type="button" className="button button--primary button--full" onClick={() => void openProject(selectedProjectSummary.project_id)}>
        Open workspace
      </button>
    </div>
  ) : (
    <div className="detail-panel">
      <div className="empty-state">Create a workspace to start drafting against bills and laws.</div>
    </div>
  );

  const billLookupMain = (
    <div className="workspace">
      <header className="page-header">
        <div>
          <div className="page-kicker">Research</div>
          <h1>Bill Lookup</h1>
          <p>
            Use normal search for precise identifiers and filtered retrieval. Use agentic search when you want Clause
            to rewrite, broaden, and rerank the search path for similar or competing bills.
          </p>
        </div>
      </header>

      <SearchToolbar
        mode={billMode}
        query={billQuery}
        filters={billFilters}
        options={billOptions}
        loading={billLoading}
        onModeChange={(nextMode) => {
          setBillMode(nextMode);
          void runBillSearch(nextMode);
        }}
        onQueryChange={setBillQuery}
        onFilterChange={handleBillFilterChange}
        onSearch={() => void runBillSearch(billMode)}
      />

      <StatsStrip stats={billStats} />
      <ResultsList response={billResponse} selectedBillId={selectedBillId} onSelect={(billId) => void handleSelectBill(billId)} />
    </div>
  );

  const billLookupDetail = billDetail ? (
    <>
      <BillDetailPanel detail={billDetail} />
      <button
        type="button"
        className="button button--primary button--full"
        onClick={() => void createProject(buildProjectFromBill(billDetail))}
      >
        Create workspace from this bill
      </button>
    </>
  ) : (
    <div className="detail-panel">
      <div className="empty-state">Select a bill to inspect the record and create a workspace from it.</div>
    </div>
  );

  const lawLookupMain = (
    <div className="workspace">
      <header className="page-header">
        <div>
          <div className="page-kicker">Research</div>
          <h1>Law Lookup</h1>
          <p>
            Use standard search for citations and exact statute text. Use agentic search when you need Clause to trace
            contradictions, constraints, or related sections across the indexed legal corpus.
          </p>
        </div>
      </header>

      <LawSearchToolbar
        mode={lawMode}
        query={lawQuery}
        filters={lawFilters}
        options={lawOptions}
        loading={lawLoading}
        onModeChange={(nextMode) => {
          setLawMode(nextMode);
          void runLawSearch(nextMode);
        }}
        onQueryChange={setLawQuery}
        onFilterChange={handleLawFilterChange}
        onSearch={() => void runLawSearch(lawMode)}
      />

      <LawStatsStrip stats={lawStats} />
      <LawResultsList response={lawResponse} selectedDocumentId={selectedLawId} onSelect={(documentId) => void handleSelectLaw(documentId)} />
    </div>
  );

  const lawLookupDetail = <LawDetailPanel detail={lawDetail} />;

  const workspaceMain = (
    <div className="workspace">
      <header className="page-header">
        <div>
          <div className="page-kicker">Workspace</div>
          <h1>{draft?.title ?? 'Bill workspace'}</h1>
          <p>
            This is the drafting surface. Save the bill text, refresh the supporting intelligence, and ask the agent to
            operate across bills, laws, and stakeholder context before you revise.
          </p>
        </div>
        <div className="page-header__actions">
          <button type="button" className="button" disabled={workspaceBusy} onClick={() => void refreshInsights()}>
            {workspaceBusy ? 'Working...' : 'Refresh analysis'}
          </button>
          <button type="button" className="button button--primary" disabled={workspaceBusy || !draft} onClick={() => void saveProject()}>
            {workspaceBusy ? 'Saving...' : 'Save draft'}
          </button>
        </div>
      </header>

      {projectLoading || !draft ? (
        <div className="empty-state">Loading workspace…</div>
      ) : (
        <>
          <section className="surface">
            <div className="surface__header">
              <div>
                <h2>Bill brief</h2>
                <p>Keep the operating context short and clear before you get into statutory text.</p>
              </div>
            </div>

            <div className="form-grid">
              <label className="form-field">
                <span>Title</span>
                <input value={draft.title} onChange={(event) => updateDraft('title', event.target.value)} />
              </label>
              <label className="form-field">
                <span>Jurisdiction</span>
                <input value={draft.jurisdiction} onChange={(event) => updateDraft('jurisdiction', event.target.value)} placeholder="California" />
              </label>
              <label className="form-field">
                <span>Stage</span>
                <input value={draft.stage} onChange={(event) => updateDraft('stage', event.target.value)} />
              </label>
              <label className="form-field">
                <span>Status</span>
                <input value={draft.status} onChange={(event) => updateDraft('status', event.target.value)} />
              </label>
              <label className="form-field form-field--full">
                <span>Policy goal</span>
                <textarea rows={3} value={draft.policy_goal} onChange={(event) => updateDraft('policy_goal', event.target.value)} />
              </label>
              <label className="form-field form-field--full">
                <span>Summary</span>
                <textarea rows={4} value={draft.summary} onChange={(event) => updateDraft('summary', event.target.value)} />
              </label>
            </div>
          </section>

          <div className="workspace-grid">
            <section className="surface">
              <div className="surface__header">
                <div>
                  <h2>Bill text</h2>
                  <p>Draft directly in the workspace. The intelligence rail is there to tighten, not distract.</p>
                </div>
              </div>
              <label className="form-field form-field--full">
                <span>Draft text</span>
                <textarea
                  className="editor-textarea"
                  rows={20}
                  value={draft.bill_text}
                  onChange={(event) => updateDraft('bill_text', event.target.value)}
                />
              </label>
              {agentResult?.revision_excerpt ? (
                <div className="explanation-banner">
                  <strong>Suggested revision excerpt:</strong> {agentResult.revision_excerpt}
                </div>
              ) : null}
            </section>

            <section className="surface">
              <div className="surface__header">
                <div>
                  <h2>Workspace agent</h2>
                  <p>Clause can search the bill and law corpora, inspect stakeholders, and come back with a revision path.</p>
                </div>
              </div>

              <div className="chat-feed">
                {projectDetail?.messages.length ? (
                  projectDetail.messages.map((message) => (
                    <article key={message.message_id} className={message.role === 'assistant' ? 'chat-bubble chat-bubble--assistant' : 'chat-bubble'}>
                      <div className="chat-bubble__role">{message.role === 'assistant' ? 'Clause agent' : 'You'}</div>
                      <p>{message.content}</p>
                    </article>
                  ))
                ) : (
                  <div className="empty-state">Ask the agent to find conflicts, peer bills, or the next revision to make.</div>
                )}
              </div>

              <label className="form-field form-field--full">
                <span>Agent request</span>
                <textarea rows={4} value={agentPrompt} onChange={(event) => setAgentPrompt(event.target.value)} />
              </label>
              <button type="button" className="button button--primary button--full" disabled={workspaceBusy} onClick={() => void sendAgentMessage()}>
                {workspaceBusy ? 'Running agent...' : 'Run Clause agent'}
              </button>
            </section>
          </div>
        </>
      )}
    </div>
  );

  const workspaceDetail = (
    <div className="detail-panel">
      <h2>{draft?.title ?? projectDetail?.title ?? 'Workspace intelligence'}</h2>
      <div className="detail-subtitle">{draft?.policy_goal ?? projectDetail?.policy_goal ?? 'Refresh analysis to populate the rail.'}</div>

      <section className="detail-card">
        <div className="detail-card__label">Drafting focus</div>
        <ul>
          {asStringList(draftingFocus?.next_actions).length ? (
            asStringList(draftingFocus?.next_actions).map((item) => <li key={item}>{item}</li>)
          ) : (
            <li>Run analysis to surface the next recommended drafting moves.</li>
          )}
        </ul>
      </section>

      <section className="detail-card">
        <div className="detail-card__label">Similar bills</div>
        <ul>
          {similarBills.length ? (
            similarBills.slice(0, 3).map((item) => (
              <li key={String(item.bill_id)}>
                <strong>{String(item.identifier)}</strong> {String(item.title)}
              </li>
            ))
          ) : (
            <li>No similar bills loaded yet.</li>
          )}
        </ul>
      </section>

      <section className="detail-card">
        <div className="detail-card__label">Conflicting laws</div>
        <ul>
          {conflictingLaws.length ? (
            conflictingLaws.slice(0, 3).map((item) => (
              <li key={String(item.document_id)}>
                <strong>{String(item.citation)}</strong> {String(item.heading ?? item.source)}
              </li>
            ))
          ) : (
            <li>No legal conflicts surfaced yet.</li>
          )}
        </ul>
      </section>

      <section className="detail-card">
        <div className="detail-card__label">Stakeholders</div>
        <ul>
          {[
            ...asStringList(stakeholders?.supporters),
            ...asStringList(stakeholders?.opponents),
          ].slice(0, 4).length ? (
            [
              ...asStringList(stakeholders?.supporters),
              ...asStringList(stakeholders?.opponents),
            ].slice(0, 4).map((item) => <li key={item}>{item}</li>)
          ) : (
            <li>Refresh the workspace to map supporters, opponents, and agencies.</li>
          )}
        </ul>
      </section>
    </div>
  );

  const routeContent = {
    home: { main: homeMain, detail: homeDetail, detailTitle: 'Selected workspace' },
    'bill-lookup': { main: billLookupMain, detail: billLookupDetail, detailTitle: 'Selected bill' },
    'law-lookup': { main: lawLookupMain, detail: lawLookupDetail, detailTitle: 'Selected law' },
    workspace: { main: workspaceMain, detail: workspaceDetail, detailTitle: 'Workspace intelligence' },
  }[route];

  return (
    <AppShell
      activeRoute={route}
      onNavigate={(nextRoute) => {
        startTransition(() => {
          setRoute(nextRoute);
        });
      }}
      user={user}
      authEnabled={authEnabled}
      onLogout={() => {
        void handleLogout();
      }}
      main={(
        <>
          {error ? <div className="error-banner error-banner--global">{error}</div> : null}
          {routeContent.main}
        </>
      )}
      detail={routeContent.detail}
      detailTitle={routeContent.detailTitle}
    />
  );
}

export default App;
