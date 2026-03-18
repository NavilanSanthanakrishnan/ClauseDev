import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, FilePenLine, Play, RefreshCcw, Send, WandSparkles } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { DiffView } from '../components/DiffView';
import { EmptyState } from '../components/EmptyState';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import { PageHeader } from '../components/PageHeader';
import { SectionFrame } from '../components/SectionFrame';
import { StatusBadge } from '../components/StatusBadge';
import { api, type Suggestion } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import { useDocumentTitle } from '../lib/useDocumentTitle';

const STAGE_ORDER = ['similar-bills', 'legal', 'stakeholders'] as const;

export function EditorPage() {
  useDocumentTitle('Draft Editor');

  const queryClient = useQueryClient();
  const { projectId } = useParams();
  const { accessToken } = useAuth();
  const [draftText, setDraftText] = useState('');
  const [changeReason, setChangeReason] = useState('Manual drafting update');
  const [steerMessage, setSteerMessage] = useState('Continue with the highest-value remaining fix.');
  const [selectedStage, setSelectedStage] = useState<(typeof STAGE_ORDER)[number]>('similar-bills');

  const draftQuery = useQuery({
    queryKey: ['draft', projectId],
    queryFn: () => api.getDraft(accessToken!, projectId!),
    enabled: Boolean(accessToken && projectId),
  });

  const versionQuery = useQuery({
    queryKey: ['draft-versions', projectId],
    queryFn: () => api.listDraftVersions(accessToken!, projectId!),
    enabled: Boolean(accessToken && projectId),
  });

  const suggestionsQuery = useQuery({
    queryKey: ['editor-suggestions', projectId],
    queryFn: () => api.getAllSuggestions(accessToken!, projectId!),
    enabled: Boolean(accessToken && projectId),
  });

  const similarReportQuery = useQuery({
    queryKey: ['editor-report', projectId, 'similar-bills'],
    queryFn: () => api.getAnalysis(accessToken!, projectId!, 'similar-bills'),
    enabled: Boolean(accessToken && projectId),
    retry: false,
  });

  const legalReportQuery = useQuery({
    queryKey: ['editor-report', projectId, 'legal'],
    queryFn: () => api.getAnalysis(accessToken!, projectId!, 'legal'),
    enabled: Boolean(accessToken && projectId),
    retry: false,
  });

  const stakeholderReportQuery = useQuery({
    queryKey: ['editor-report', projectId, 'stakeholders'],
    queryFn: () => api.getAnalysis(accessToken!, projectId!, 'stakeholders'),
    enabled: Boolean(accessToken && projectId),
    retry: false,
  });

  const editorSessionQuery = useQuery({
    queryKey: ['editor-session', projectId],
    queryFn: () => api.getEditorSession(accessToken!, projectId!),
    enabled: Boolean(accessToken && projectId),
    retry: false,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ['running', 'waiting_approval'].includes(status) ? 1500 : false;
    },
  });

  const editorEventsQuery = useQuery({
    queryKey: ['editor-events', projectId],
    queryFn: () => api.listEditorSessionEvents(accessToken!, projectId!),
    enabled: Boolean(accessToken && projectId && editorSessionQuery.data?.session_id),
    retry: false,
    refetchInterval: editorSessionQuery.data?.status && ['running', 'waiting_approval'].includes(editorSessionQuery.data.status) ? 1500 : false,
  });

  useEffect(() => {
    if (draftQuery.data?.current_text) {
      setDraftText(draftQuery.data.current_text);
    }
  }, [draftQuery.data?.current_text]);

  const groupedSuggestions = (suggestionsQuery.data ?? []).reduce<Record<string, Suggestion[]>>((acc, item) => {
    acc[item.stage_name] ??= [];
    acc[item.stage_name].push(item);
    return acc;
  }, {});

  const saveMutation = useMutation({
    mutationFn: () =>
      api.saveDraftVersion(accessToken!, projectId!, {
        content_text: draftText,
        change_reason: changeReason,
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['draft', projectId] }),
        queryClient.invalidateQueries({ queryKey: ['draft-versions', projectId] }),
      ]);
    },
  });

  const restoreMutation = useMutation({
    mutationFn: (versionId: string) => api.restoreDraftVersion(accessToken!, projectId!, versionId),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['draft', projectId] }),
        queryClient.invalidateQueries({ queryKey: ['draft-versions', projectId] }),
      ]);
    },
  });

  const startSessionMutation = useMutation({
    mutationFn: () => api.startEditorSession(accessToken!, projectId!),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['editor-session', projectId] }),
        queryClient.invalidateQueries({ queryKey: ['editor-events', projectId] }),
      ]);
    },
  });

  const steerMutation = useMutation({
    mutationFn: () => api.steerEditorSession(accessToken!, projectId!, { message: steerMessage }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['editor-session', projectId] }),
        queryClient.invalidateQueries({ queryKey: ['editor-events', projectId] }),
      ]);
      setSteerMessage('');
    },
  });

  const approveMutation = useMutation({
    mutationFn: () => api.approveEditorDiff(accessToken!, projectId!),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['editor-session', projectId] }),
        queryClient.invalidateQueries({ queryKey: ['editor-events', projectId] }),
        queryClient.invalidateQueries({ queryKey: ['draft', projectId] }),
        queryClient.invalidateQueries({ queryKey: ['draft-versions', projectId] }),
      ]);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => api.rejectEditorDiff(accessToken!, projectId!),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['editor-session', projectId] }),
        queryClient.invalidateQueries({ queryKey: ['editor-events', projectId] }),
      ]);
    },
  });

  const reports = {
    'similar-bills': similarReportQuery.data?.markdown_content ?? 'No saved similar-bills report yet.',
    legal: legalReportQuery.data?.markdown_content ?? 'No saved legal report yet.',
    stakeholders: stakeholderReportQuery.data?.markdown_content ?? 'No saved stakeholder report yet.',
  };

  const session = editorSessionQuery.data;
  const pendingApproval = session?.pending_approval ?? {};

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Final Drafting Workspace"
        title="Approve changes, save versions, and finish the bill."
        description="Analysis stays visible while the final Codex drafting loop proposes changes to the live bill text."
        badges={
          <>
            <StatusBadge tone="info">{session?.status ?? 'idle'}</StatusBadge>
            <StatusBadge tone="neutral">{`${versionQuery.data?.length ?? 0} saved versions`}</StatusBadge>
          </>
        }
        actions={
          <div className="button-row">
            <button
              type="button"
              className="button button-primary"
              onClick={() => startSessionMutation.mutate()}
              disabled={startSessionMutation.isPending || !projectId}
            >
              <Play size={16} />
              {startSessionMutation.isPending ? 'Starting Codex...' : 'Start Codex Session'}
            </button>
            <button type="button" className="button button-secondary" onClick={() => api.downloadDraft(accessToken!, projectId!, 'txt')}>
              <Download size={16} />
              Export TXT
            </button>
            <button type="button" className="button button-secondary" onClick={() => api.downloadDraft(accessToken!, projectId!, 'docx')}>
              <Download size={16} />
              Export DOCX
            </button>
          </div>
        }
      />

      {startSessionMutation.error instanceof Error ? (
        <div className="form-error">{startSessionMutation.error.message}</div>
      ) : null}
      {session?.error_message ? <div className="form-error">{session.error_message}</div> : null}

      <div className="page-grid editor-workspace-layout">
        <div className="rail-stack">
          <SectionFrame
            eyebrow="Analysis"
            title="Saved reports and guidance"
            description="The final editor should stay anchored to the saved analysis and guidance, while actual edits only happen through the live Codex loop."
            icon={WandSparkles}
          >
            <div className="analysis-tab-row">
              {STAGE_ORDER.map((stage) => (
                <button
                  key={stage}
                  type="button"
                  className={`analysis-tab${selectedStage === stage ? ' active' : ''}`}
                  onClick={() => setSelectedStage(stage)}
                >
                  {formatStage(stage)}
                </button>
              ))}
            </div>
            <div className="markdown-reading compact-markdown">
              <MarkdownRenderer content={reports[selectedStage]} />
            </div>
            <div className="suggestion-list compact-suggestion-list">
              {(groupedSuggestions[selectedStage] ?? []).map((suggestion) => (
                <article key={suggestion.suggestion_id} className="suggestion-card">
                  <div className="suggestion-top">
                    <strong>{suggestion.title}</strong>
                    <StatusBadge>{suggestion.status}</StatusBadge>
                  </div>
                  <p>{suggestion.rationale}</p>
                  {suggestion.source_refs.length ? (
                    <div className="reading-pane compact diff-block">
                      <strong>Supporting sources</strong>
                      {'\n'}
                      {suggestion.source_refs
                        .map((source) => String(source.identifier ?? source.citation ?? source.name ?? 'Saved source'))
                        .join('\n')}
                    </div>
                  ) : null}
                </article>
              ))}
              {!groupedSuggestions[selectedStage]?.length ? (
                <EmptyState icon={WandSparkles} title="No saved guidance" description="Run the earlier workflow stages to save guidance for this section." />
              ) : null}
            </div>
          </SectionFrame>

          <SectionFrame
            eyebrow="Version history"
            title="Restore a saved version"
            description="Each save and each accepted AI edit creates a new version you can return to."
            icon={RefreshCcw}
          >
            <div className="version-list">
              {versionQuery.data?.map((version) => (
                <button
                  key={version.version_id}
                  type="button"
                  className="version-row"
                  onClick={() => restoreMutation.mutate(version.version_id)}
                >
                  <div className="result-row-top">
                    <StatusBadge tone="info">{`v${version.version_number}`}</StatusBadge>
                    <span className="mono-note">{version.source_kind}</span>
                  </div>
                  <strong>{String(version.change_summary.reason ?? 'Saved version')}</strong>
                  <p>{new Date(version.created_at).toLocaleString()}</p>
                </button>
              ))}
            </div>
          </SectionFrame>
        </div>

        <SectionFrame
          eyebrow="Bill Draft"
          title={draftQuery.data?.title ?? 'Current draft'}
          description="Manual edits remain available at all times. Save checkpoints as you work."
          icon={FilePenLine}
        >
          <div className="field-stack">
            <label className="field">
              <span className="field-label">Why are you saving this version?</span>
              <input value={changeReason} onChange={(event) => setChangeReason(event.target.value)} />
            </label>
            <label className="field">
              <span className="field-label">Bill text</span>
              <textarea className="editor-textarea" value={draftText} onChange={(event) => setDraftText(event.target.value)} />
            </label>
            <button
              type="button"
              className="button button-primary"
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending || !draftText.trim()}
            >
              <FilePenLine size={16} />
              {saveMutation.isPending ? 'Saving version...' : 'Save version'}
            </button>
          </div>
        </SectionFrame>

        <div className="rail-stack">
          <SectionFrame
            eyebrow="Live Codex Session"
            title="Agent loop and approvals"
            description="The final drafting agent works from the saved reports and proposes bill edits one at a time."
            icon={Play}
          >
            <div className="detail-stack">
              <div className="badge-row">
                <StatusBadge tone="info">{session?.status ?? 'idle'}</StatusBadge>
                <StatusBadge tone="neutral">{formatStage(session?.current_stage ?? 'similar-bills')}</StatusBadge>
              </div>
              {session?.latest_agent_message ? <div className="reading-pane compact">{session.latest_agent_message}</div> : null}
              {pendingApproval.diff ? (
                <div className="approval-card">
                  <div className="page-eyebrow">Pending approval</div>
                  <DiffView diff={String(pendingApproval.diff)} />
                  <div className="button-row">
                    <button type="button" className="button button-primary" onClick={() => approveMutation.mutate()} disabled={approveMutation.isPending}>
                      Approve change
                    </button>
                    <button type="button" className="button button-secondary" onClick={() => rejectMutation.mutate()} disabled={rejectMutation.isPending}>
                      Reject change
                    </button>
                  </div>
                </div>
              ) : null}
              <label className="field">
                <span className="field-label">Steer the active session</span>
                <textarea
                  rows={6}
                  value={steerMessage}
                  onChange={(event) => setSteerMessage(event.target.value)}
                  placeholder="Tell Codex what to prioritize next."
                />
              </label>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => steerMutation.mutate()}
                disabled={steerMutation.isPending || !steerMessage.trim() || !session || session.status === 'error'}
              >
                <Send size={16} />
                {steerMutation.isPending ? 'Sending...' : 'Send steer'}
              </button>
            </div>
          </SectionFrame>

          <SectionFrame
            eyebrow="Timeline"
            title="Session events"
            description="This is the durable activity trace for the final drafting loop."
            icon={WandSparkles}
          >
            <div className="activity-list">
              {editorEventsQuery.data?.map((item) => (
                <article key={item.event_id} className="activity-row">
                  <div className="activity-row-top">
                    <strong>{item.title}</strong>
                    <StatusBadge>{item.kind}</StatusBadge>
                  </div>
                  <p>{item.body || 'No event body.'}</p>
                  <span className="mono-note">{new Date(item.created_at).toLocaleString()}</span>
                </article>
              ))}
              {!editorEventsQuery.data?.length ? (
                <EmptyState icon={WandSparkles} title="No editor events yet" description="Start the Codex session to begin the final drafting loop." />
              ) : null}
            </div>
          </SectionFrame>
        </div>
      </div>
    </div>
  );
}

function formatStage(stageName: string) {
  if (stageName === 'similar-bills') {
    return 'Similar Bills';
  }
  return stageName
    .split('-')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
}
