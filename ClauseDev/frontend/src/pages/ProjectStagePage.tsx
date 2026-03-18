import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  FileSearch,
  FileText,
  LibraryBig,
  Rocket,
  ScanText,
  ShieldAlert,
  Upload,
  Users,
  WandSparkles,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { Dispatch, SetStateAction } from 'react';
import { useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';

import { EmptyState } from '../components/EmptyState';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import { NextStepCard } from '../components/NextStepCard';
import { PageHeader } from '../components/PageHeader';
import { SectionFrame } from '../components/SectionFrame';
import { StatusBadge } from '../components/StatusBadge';
import { WorkflowStageNav } from '../components/WorkflowStageNav';
import { api, type PipelineRun } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import {
  type AnalysisStageKey,
  type WorkflowPageKey,
  getWorkflowPageKeyFromPath,
  getWorkflowPages,
  workflowPageDefinitions,
} from '../lib/stages';
import { useDocumentTitle } from '../lib/useDocumentTitle';

const RUNNABLE_STAGES = new Set<WorkflowPageKey>(['metadata', 'similar-bills', 'legal', 'stakeholders']);

const pageIcons: Record<WorkflowPageKey, LucideIcon> = {
  upload: Upload,
  extraction: ScanText,
  metadata: FileText,
  'similar-bills': LibraryBig,
  'similar-bills-report': FileText,
  'similar-bills-fixes': WandSparkles,
  legal: ShieldAlert,
  'legal-report': FileText,
  'legal-fixes': WandSparkles,
  stakeholders: Users,
  'stakeholders-report': FileSearch,
  'stakeholders-fixes': WandSparkles,
  editor: FileText,
};

export function ProjectStagePage() {
  const { projectId } = useParams();
  const location = useLocation();
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const currentPageKey = getWorkflowPageKeyFromPath(location.pathname);
  const currentPage = workflowPageDefinitions.find((page) => page.key === currentPageKey) ?? workflowPageDefinitions[0];
  const analysisStage = isAnalysisStage(currentPage.coreStage) ? currentPage.coreStage : null;
  const workflowPages = projectId ? getWorkflowPages(projectId) : [];
  const currentPageIndex = workflowPages.findIndex((page) => page.key === currentPageKey);
  const previousPage = currentPageIndex > 0 ? workflowPages[currentPageIndex - 1] : null;
  const nextPage = currentPageIndex >= 0 ? workflowPages[currentPageIndex + 1] ?? null : null;

  const [selectedResultIndex, setSelectedResultIndex] = useState(0);
  const [metadataForm, setMetadataForm] = useState({
    title: '',
    description: '',
    summary: '',
    keywords: '',
    policy_area: '',
    affected_entities: '',
  });
  const [metadataDirty, setMetadataDirty] = useState(false);

  useDocumentTitle(currentPage.navLabel);

  const documentQuery = useQuery({
    queryKey: ['document', projectId],
    queryFn: () => api.getLatestSourceDocument(accessToken!, projectId!),
    enabled: Boolean(accessToken && projectId),
    retry: false,
  });

  const pipelineRunsQuery = useQuery({
    queryKey: ['pipeline-runs', projectId],
    queryFn: () => api.listPipelineRuns(accessToken!, projectId!),
    enabled: Boolean(accessToken && projectId),
    retry: false,
    refetchInterval: (query) => (
      query.state.data?.some((run) => run.status === 'running')
        ? 1500
        : false
    ),
  });

  const metadataQuery = useQuery({
    queryKey: ['metadata', projectId],
    queryFn: () => api.getMetadata(accessToken!, projectId!),
    enabled: Boolean(accessToken && projectId && currentPageKey !== 'upload'),
    retry: false,
  });

  const latestStageRun = getLatestStageRun(pipelineRunsQuery.data, analysisStage);
  const analysisOutputsReady = latestStageRun?.status === 'completed';
  const analysisStageIsRunning = latestStageRun?.status === 'running';

  const artifactQuery = useQuery({
    queryKey: ['artifact', projectId, analysisStage],
    queryFn: () => api.getAnalysis(accessToken!, projectId!, analysisStage!),
    enabled: Boolean(accessToken && projectId && analysisStage && analysisOutputsReady),
    retry: false,
  });

  const suggestionsQuery = useQuery({
    queryKey: ['suggestions', projectId, analysisStage],
    queryFn: () => api.getSuggestions(accessToken!, projectId!, analysisStage!),
    enabled: Boolean(accessToken && projectId && analysisStage && analysisOutputsReady),
    retry: false,
  });

  const pipelineMutation = useMutation({
    mutationFn: (stageName: string) => api.startPipelineRun(accessToken!, projectId!, stageName),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['metadata', projectId] }),
        queryClient.invalidateQueries({ queryKey: ['pipeline-runs', projectId] }),
        queryClient.invalidateQueries({ queryKey: ['artifact', projectId, analysisStage] }),
        queryClient.invalidateQueries({ queryKey: ['suggestions', projectId, analysisStage] }),
      ]);
    },
  });

  const saveMetadataMutation = useMutation({
    mutationFn: () =>
      api.updateMetadata(accessToken!, projectId!, {
        title: displayMetadataForm.title,
        description: displayMetadataForm.description,
        summary: displayMetadataForm.summary,
        keywords: displayMetadataForm.keywords
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
        extras: {
          policy_area: displayMetadataForm.policy_area,
          affected_entities: displayMetadataForm.affected_entities
            .split(',')
            .map((item) => item.trim())
            .filter(Boolean),
        },
      }),
    onSuccess: async () => {
      setMetadataDirty(false);
      await queryClient.invalidateQueries({ queryKey: ['metadata', projectId] });
    },
  });

  const selectedResult = getSelectedResult(artifactQuery.data?.payload_json?.items, selectedResultIndex);
  const displayMetadataForm = metadataDirty ? metadataForm : deriveMetadataForm(metadataQuery.data);
  const stageDataIsLoading = Boolean(
    analysisStage && (pipelineRunsQuery.isLoading || artifactQuery.isLoading || suggestionsQuery.isLoading),
  );

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Bill Workflow"
        title={currentPage.title}
        description={currentPage.summary}
        badges={
          <>
            <StatusBadge tone="info">{currentPage.navLabel}</StatusBadge>
            <StatusBadge tone="neutral">{`Page ${Math.max(currentPageIndex + 1, 1)} of ${workflowPages.length || 1}`}</StatusBadge>
          </>
        }
        actions={
          RUNNABLE_STAGES.has(currentPage.key) ? (
            <button
              type="button"
              className="button button-primary"
              onClick={() => pipelineMutation.mutate(currentPage.coreStage)}
              disabled={pipelineMutation.isPending || !projectId}
            >
              <Rocket size={16} />
              {pipelineMutation.isPending ? 'Running...' : getRunButtonLabel(currentPage.key)}
            </button>
          ) : null
        }
      />

      <div className="page-grid stage-layout">
        <div className="page-stack">
          {currentPageKey === 'upload' ? (
            <>
              <SectionFrame
                eyebrow="Step 1"
                title="Upload your bill"
                description="Upload the source bill as DOCX, PDF, or TXT. Extraction happens immediately and is saved to the workspace."
                icon={Upload}
              >
                <UploadWidget projectId={projectId ?? ''} />
              </SectionFrame>
              <StageNotes
                title="What happens next"
                lines={[
                  'Review the extracted text before you trust the rest of the workflow.',
                  'Generate metadata only after the source text looks correct.',
                  'Nothing downstream should start from a bad extraction.',
                ]}
              />
            </>
          ) : null}

          {currentPageKey === 'extraction' ? (
            <SectionFrame
              eyebrow="Step 2"
              title="Review the extracted text"
              description="This is the source text that powers metadata generation and every later report."
              icon={ScanText}
            >
              {documentQuery.isLoading ? <div className="loading-line">Loading extracted text...</div> : null}
              {documentQuery.data?.filename ? (
                <div className="badge-row">
                  <StatusBadge tone="info">{documentQuery.data.filename}</StatusBadge>
                  {documentQuery.data.file_type ? <StatusBadge tone="neutral">{documentQuery.data.file_type}</StatusBadge> : null}
                </div>
              ) : null}
              <pre className="reading-pane">{documentQuery.data?.extracted_text ?? 'Upload a source document first.'}</pre>
              <div className="button-row">
                <Link to={`/projects/${projectId}/metadata`} className="button button-secondary">Open Metadata</Link>
                <button
                  type="button"
                  className="button button-primary"
                  onClick={() => pipelineMutation.mutate('metadata')}
                  disabled={pipelineMutation.isPending}
                >
                  Generate Metadata
                </button>
              </div>
            </SectionFrame>
          ) : null}

          {currentPageKey === 'metadata' ? (
            <SectionFrame
              eyebrow="Step 3"
              title="Edit the bill metadata"
              description="This metadata drives similar-bill retrieval and helps frame the downstream analysis reports."
              icon={FileText}
              actions={
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => saveMetadataMutation.mutate()}
                  disabled={saveMetadataMutation.isPending}
                >
                  {saveMetadataMutation.isPending ? 'Saving...' : 'Save metadata'}
                </button>
              }
            >
              <div className="field-grid">
                <label className="field field-full">
                  <span className="field-label">Bill title</span>
                  <input value={displayMetadataForm.title} onChange={(event) => updateForm(setMetadataForm, setMetadataDirty, displayMetadataForm, 'title', event.target.value)} />
                </label>
                <label className="field">
                  <span className="field-label">Policy area</span>
                  <input value={displayMetadataForm.policy_area} onChange={(event) => updateForm(setMetadataForm, setMetadataDirty, displayMetadataForm, 'policy_area', event.target.value)} />
                </label>
                <label className="field">
                  <span className="field-label">Affected entities</span>
                  <input
                    value={displayMetadataForm.affected_entities}
                    onChange={(event) => updateForm(setMetadataForm, setMetadataDirty, displayMetadataForm, 'affected_entities', event.target.value)}
                    placeholder="e.g. hospitals, insurers, local agencies"
                  />
                </label>
                <label className="field field-full">
                  <span className="field-label">Description</span>
                  <textarea rows={4} value={displayMetadataForm.description} onChange={(event) => updateForm(setMetadataForm, setMetadataDirty, displayMetadataForm, 'description', event.target.value)} />
                </label>
                <label className="field field-full">
                  <span className="field-label">Summary</span>
                  <textarea rows={6} value={displayMetadataForm.summary} onChange={(event) => updateForm(setMetadataForm, setMetadataDirty, displayMetadataForm, 'summary', event.target.value)} />
                </label>
                <label className="field field-full">
                  <span className="field-label">Keywords</span>
                  <input
                    value={displayMetadataForm.keywords}
                    onChange={(event) => updateForm(setMetadataForm, setMetadataDirty, displayMetadataForm, 'keywords', event.target.value)}
                    placeholder="comma separated"
                  />
                </label>
              </div>
            </SectionFrame>
          ) : null}

          {currentPageKey === 'similar-bills' ? (
            <div className="page-grid results-layout">
              <SectionFrame
                eyebrow="Step 4"
                title="Similar bills search"
                description="Run the similar-bill search, inspect the matches, and then move into the saved analysis report."
                icon={LibraryBig}
              >
                {pipelineMutation.error instanceof Error ? <div className="form-error">{pipelineMutation.error.message}</div> : null}
                {analysisStageIsRunning ? <div className="loading-line">Search is running and the saved results will appear here when the stage completes.</div> : null}
                {stageDataIsLoading && !artifactQuery.data ? <div className="loading-line">Loading saved search results...</div> : null}
                <div className="result-list">
                  {Array.isArray(artifactQuery.data?.payload_json?.items) ? (
                    (artifactQuery.data?.payload_json?.items as Array<Record<string, unknown>>).map((item, index) => (
                      <button
                        key={`${String(item.bill_id ?? item.identifier ?? index)}`}
                        type="button"
                        className={`result-row${selectedResultIndex === index ? ' active' : ''}`}
                        onClick={() => setSelectedResultIndex(index)}
                      >
                        <div className="result-row-top">
                          <StatusBadge>{String(item.derived_status ?? 'unknown')}</StatusBadge>
                          <span className="mono-note">{String(item.state_code ?? item.jurisdiction_name ?? 'jurisdiction')}</span>
                        </div>
                        <strong>{String(item.title ?? 'Untitled bill')}</strong>
                        <p>{String(item.identifier ?? '')}</p>
                        <p>{String(item.summary_text ?? item.summary ?? item.excerpt ?? 'No summary available.')}</p>
                      </button>
                    ))
                  ) : (
                    <EmptyState
                      icon={LibraryBig}
                      title="No similar bills yet"
                      description="Run the similar-bill search to populate the research panel."
                    />
                  )}
                </div>
              </SectionFrame>

              <SectionFrame
                eyebrow="Selected bill"
                title="Bill detail"
                description="Use this pane to compare the current draft against the strongest precedent match."
                icon={LibraryBig}
              >
                {selectedResult ? (
                  <div className="detail-stack">
                    <div className="detail-header">
                      <div className="detail-badges">
                        <StatusBadge>{String(selectedResult.derived_status ?? 'unknown')}</StatusBadge>
                        {selectedResult.primary_source_url ? (
                          <a href={String(selectedResult.primary_source_url)} target="_blank" rel="noreferrer" className="button button-secondary">
                            Open source
                          </a>
                        ) : null}
                      </div>
                      <h3 className="detail-title">{String(selectedResult.title ?? 'Untitled bill')}</h3>
                      <p className="detail-meta">{String(selectedResult.identifier ?? '')} · {String(selectedResult.jurisdiction_name ?? '')}</p>
                    </div>
                    <div className="reading-pane compact">{String(selectedResult.summary_text ?? selectedResult.summary ?? selectedResult.structured_summary ?? 'No summary available.')}</div>
                    <div className="reading-pane">{String(selectedResult.full_text ?? selectedResult.excerpt ?? 'No full text available in the saved corpus.')}</div>
                  </div>
                ) : (
                  <EmptyState icon={LibraryBig} title="No bill selected" description="Pick a bill from the list to inspect it here." />
                )}
              </SectionFrame>
            </div>
          ) : null}

          {currentPageKey === 'legal' ? (
            <AnalysisOverview
              eyebrow="Step 5"
              title="Legal conflict analysis"
              description="Run the legal conflict stage to identify conflicting statutes and generate a traceable legal report."
              icon={ShieldAlert}
              payload={artifactQuery.data?.payload_json}
              emptyTitle="No legal report yet"
              emptyDescription={latestStageRun?.status === 'running'
                ? 'The legal stage is still running. This page will populate when the saved report is ready.'
                : 'Run the legal conflict stage to populate this page.'}
            />
          ) : null}

          {currentPageKey === 'stakeholders' ? (
            <AnalysisOverview
              eyebrow="Step 6"
              title="Stakeholder analysis"
              description="Run the stakeholder stage to surface likely support, opposition, and language changes to reduce friction."
              icon={Users}
              payload={artifactQuery.data?.payload_json}
              emptyTitle="No stakeholder report yet"
              emptyDescription={latestStageRun?.status === 'running'
                ? 'The stakeholder stage is still running. This page will populate when the saved report is ready.'
                : 'Run the stakeholder stage to populate this page.'}
            />
          ) : null}

          {currentPageKey.endsWith('report') ? (
            <SectionFrame
              eyebrow="Saved report"
              title={currentPage.title}
              description="Read the structured report first. The next page isolates the general drafting guidance."
              icon={FileText}
            >
              {stageDataIsLoading && !artifactQuery.data?.markdown_content ? (
                <div className="loading-line">Loading saved report...</div>
              ) : artifactQuery.data?.markdown_content ? (
                <div className="markdown-reading">
                  <MarkdownRenderer content={artifactQuery.data.markdown_content} />
                </div>
              ) : (
                <EmptyState
                  icon={FileText}
                  title="No report yet"
                  description="Go back one page and run the analysis to generate this report."
                />
              )}
            </SectionFrame>
          ) : null}

          {currentPageKey.endsWith('fixes') ? (
            <SectionFrame
              eyebrow="Saved guidance"
              title={currentPage.title}
              description="These are the saved drafting directions that will feed the final drafting workspace."
              icon={WandSparkles}
            >
              {stageDataIsLoading && !suggestionsQuery.data?.length ? (
                <div className="loading-line">Loading saved guidance...</div>
              ) : suggestionsQuery.data?.length ? (
                <div className="suggestion-list">
                  {suggestionsQuery.data.map((suggestion) => (
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
                </div>
              ) : (
                <EmptyState
                  icon={WandSparkles}
                  title="No saved guidance yet"
                  description={latestStageRun?.status === 'running'
                    ? 'The stage is still running. The saved guidance will appear here when it finishes.'
                    : 'Run the stage before this page to generate saved guidance.'}
                />
              )}
            </SectionFrame>
          ) : null}
        </div>

        <aside className="rail-stack">
          <SectionFrame
            eyebrow="Workflow"
            title="Move through the pages"
            description="The workflow is explicit. Every page exists for one job."
            icon={pageIcons[currentPageKey]}
          >
            {projectId ? <WorkflowStageNav projectId={projectId} currentPage={currentPageKey} /> : null}
          </SectionFrame>

          {documentQuery.data?.filename ? (
            <SectionFrame
              eyebrow="Workspace file"
              title="Current source document"
              description="The uploaded source file stays attached to the bill workspace."
              icon={FileText}
            >
              <div className="detail-stack">
                <StatusBadge tone="info">{documentQuery.data.filename}</StatusBadge>
                {documentQuery.data.file_type ? <StatusBadge tone="neutral">{documentQuery.data.file_type}</StatusBadge> : null}
              </div>
            </SectionFrame>
          ) : null}

          {previousPage ? (
            <NextStepCard
              to={previousPage.to}
              title={previousPage.navLabel}
              description={previousPage.summary}
              icon={pageIcons[previousPage.key]}
              direction="previous"
            />
          ) : null}

          {nextPage ? (
            <NextStepCard
              to={nextPage.to}
              title={nextPage.navLabel}
              description={nextPage.summary}
              icon={pageIcons[nextPage.key]}
            />
          ) : null}
        </aside>
      </div>
    </div>
  );
}

function getLatestStageRun(runs: PipelineRun[] | undefined, stageName: AnalysisStageKey | null) {
  if (!stageName || !runs?.length) {
    return null;
  }
  const matchingRuns = runs.filter((run) => run.stage_name === stageName);
  if (!matchingRuns.length) {
    return null;
  }
  return matchingRuns
    .slice()
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())[0] ?? null;
}

function UploadWidget({ projectId }: { projectId: string }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const latestDocumentQuery = useQuery({
    queryKey: ['document', projectId],
    queryFn: () => api.getLatestSourceDocument(accessToken!, projectId),
    enabled: Boolean(accessToken && projectId),
    retry: false,
  });
  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadSourceDocument(accessToken!, projectId, file),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['document', projectId] });
    },
  });

  return (
    <div className="upload-stage">
      <label className="upload-dropzone">
        <input
          type="file"
          accept=".txt,.pdf,.docx"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) {
              uploadMutation.mutate(file);
            }
          }}
        />
        <div className="upload-dropzone-inner">
          <div className="upload-title">Upload Your Bill</div>
          <div className="upload-subtitle">DOCX, PDF, TXT</div>
        </div>
      </label>
      {uploadMutation.isPending ? <div className="loading-line">Extracting text from the uploaded bill...</div> : null}
      {latestDocumentQuery.data?.filename ? (
        <div className="badge-row">
          <StatusBadge tone="info">{latestDocumentQuery.data.filename}</StatusBadge>
          {latestDocumentQuery.data.file_type ? <StatusBadge tone="neutral">{latestDocumentQuery.data.file_type}</StatusBadge> : null}
        </div>
      ) : null}
      <pre className="reading-pane">{uploadMutation.data?.extracted_text ?? latestDocumentQuery.data?.extracted_text ?? 'The extracted text preview appears here after upload.'}</pre>
      <Link to={`/projects/${projectId}/extraction`} className="button button-secondary">Open Extracted Text</Link>
    </div>
  );
}

function AnalysisOverview({
  eyebrow,
  title,
  description,
  icon,
  payload,
  emptyTitle,
  emptyDescription,
}: {
  eyebrow: string;
  title: string;
  description: string;
  icon: LucideIcon;
  payload: Record<string, unknown> | undefined;
  emptyTitle: string;
  emptyDescription: string;
}) {
  const items = Array.isArray(payload?.items) ? (payload?.items as Array<Record<string, unknown>>) : [];
  return (
    <SectionFrame eyebrow={eyebrow} title={title} description={description} icon={icon}>
      {items.length ? (
        <div className="analysis-card-grid">
          {items.map((item, index) => (
            <article key={`${title}-${index}`} className="analysis-glance-card">
              <div className="result-row-top">
                <StatusBadge>{String(item.priority ?? item.risk_level ?? item.stance ?? 'saved')}</StatusBadge>
              </div>
              <strong>{String(item.name ?? item.citation ?? item.title ?? 'Saved context')}</strong>
              <p>{String(item.reason ?? item.heading ?? item.summary ?? item.body_excerpt ?? 'No detail available.')}</p>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState icon={icon} title={emptyTitle} description={emptyDescription} />
      )}
    </SectionFrame>
  );
}

function StageNotes({ title, lines }: { title: string; lines: string[] }) {
  return (
    <SectionFrame eyebrow="Notes" title={title} description="The workflow is intentionally rigid so each stage stays understandable." icon={FileText}>
      <div className="simple-list numbered">
        {lines.map((line, index) => (
          <div key={line} className="simple-list-row">
            <strong>{index + 1}.</strong>
            <span>{line}</span>
          </div>
        ))}
      </div>
    </SectionFrame>
  );
}

function getSelectedResult(rawItems: unknown, selectedResultIndex: number) {
  if (!Array.isArray(rawItems)) {
    return null;
  }
  return (rawItems[selectedResultIndex] ?? rawItems[0] ?? null) as Record<string, unknown> | null;
}

function updateForm(
  setForm: Dispatch<SetStateAction<{
    title: string;
    description: string;
    summary: string;
    keywords: string;
    policy_area: string;
    affected_entities: string;
  }>>,
  setDirty: Dispatch<SetStateAction<boolean>>,
  currentForm: {
    title: string;
    description: string;
    summary: string;
    keywords: string;
    policy_area: string;
    affected_entities: string;
  },
  key: 'title' | 'description' | 'summary' | 'keywords' | 'policy_area' | 'affected_entities',
  value: string,
) {
  setDirty(true);
  setForm({ ...currentForm, [key]: value });
}

function deriveMetadataForm(metadata: {
  title: string;
  description: string;
  summary: string;
  keywords: string[];
  extras: Record<string, unknown>;
} | undefined) {
  return {
    title: metadata?.title ?? '',
    description: metadata?.description ?? '',
    summary: metadata?.summary ?? '',
    keywords: metadata?.keywords.join(', ') ?? '',
    policy_area: String(metadata?.extras?.policy_area ?? ''),
    affected_entities: Array.isArray(metadata?.extras?.affected_entities)
      ? (metadata?.extras?.affected_entities as string[]).join(', ')
      : String(metadata?.extras?.affected_entities ?? ''),
  };
}

function isAnalysisStage(stage: string): stage is AnalysisStageKey {
  return stage === 'similar-bills' || stage === 'legal' || stage === 'stakeholders';
}

function getRunButtonLabel(pageKey: WorkflowPageKey) {
  switch (pageKey) {
    case 'metadata':
      return 'Generate Metadata';
    case 'similar-bills':
      return 'Run Similar Bills Search';
    case 'legal':
      return 'Run Legal Conflict Analysis';
    case 'stakeholders':
      return 'Run Stakeholder Analysis';
    default:
      return 'Run This Stage';
  }
}
