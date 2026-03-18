import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, FilePlus2, FolderOpen, Plus, ScrollText } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { EmptyState } from '../components/EmptyState';
import { NextStepCard } from '../components/NextStepCard';
import { PageHeader } from '../components/PageHeader';
import { SectionFrame } from '../components/SectionFrame';
import { StatusBadge } from '../components/StatusBadge';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth-context';
import { formatStageLabel } from '../lib/stages';
import { useDocumentTitle } from '../lib/useDocumentTitle';

const jurisdictionOptions = [
  { value: 'state', label: 'State bill' },
  { value: 'federal', label: 'Federal bill' },
  { value: 'local', label: 'Local ordinance' },
];

export function BillsHomePage() {
  useDocumentTitle('Workspaces');

  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const [title, setTitle] = useState('California Clean Transit Access Act');
  const [jurisdictionType, setJurisdictionType] = useState('state');
  const [jurisdictionName, setJurisdictionName] = useState('California');
  const [initialText, setInitialText] = useState('');

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: () => api.listProjects(accessToken!),
    enabled: Boolean(accessToken),
  });

  const createProject = useMutation({
    mutationFn: () =>
      api.createProject(accessToken!, {
        title,
        jurisdiction_type: jurisdictionType,
        jurisdiction_name: jurisdictionName,
        initial_text: initialText,
      }),
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: ['projects'] });
      navigate(`/projects/${project.project_id}/upload`);
    },
  });

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Your Bills"
        title="Create a bill workspace or jump back into one."
        description="Each bill is a saved drafting workflow: upload, extract, metadata, similar bills, legal conflicts, stakeholders, then the final editor."
        badges={
          <>
            <StatusBadge tone="info">{`${projectsQuery.data?.length ?? 0} saved workspaces`}</StatusBadge>
            <StatusBadge tone="neutral">State saved in PostgreSQL</StatusBadge>
          </>
        }
      />

      <div className="page-grid two-column">
        <SectionFrame
          eyebrow="New workspace"
          title="Start a new bill workspace"
          description="Name the bill, pick the jurisdiction, and optionally paste opening language before you upload the full file."
          icon={FilePlus2}
          actions={
            <button
              type="button"
              className="button button-primary"
              onClick={() => createProject.mutate()}
              disabled={createProject.isPending}
            >
              <ArrowRight size={16} />
              {createProject.isPending ? 'Creating workspace...' : 'Create workspace'}
            </button>
          }
        >
          <div className="field-grid">
            <label className="field">
              <span className="field-label">Bill title</span>
              <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. California Clean Transit Access Act" />
            </label>
            <label className="field">
              <span className="field-label">Jurisdiction type</span>
              <select value={jurisdictionType} onChange={(event) => setJurisdictionType(event.target.value)}>
                {jurisdictionOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field-label">Jurisdiction name</span>
              <input value={jurisdictionName} onChange={(event) => setJurisdictionName(event.target.value)} placeholder="e.g. California" />
            </label>
            <label className="field field-full">
              <span className="field-label">Starting draft text</span>
              <textarea
                rows={8}
                value={initialText}
                onChange={(event) => setInitialText(event.target.value)}
                placeholder="Paste the opening section here if you already have draft language."
              />
            </label>
          </div>
          {createProject.error ? (
            <div className="form-error">
              {createProject.error instanceof Error ? createProject.error.message : 'Unable to create the workspace.'}
            </div>
          ) : null}
        </SectionFrame>

        <SectionFrame
          eyebrow="Workflow"
          title="Follow the same path every time"
          description="The analysis pipeline always happens before the live drafting workspace."
          icon={ScrollText}
        >
          <div className="simple-list numbered">
            <div className="simple-list-row"><strong>1.</strong><span>Upload the source bill and review extraction.</span></div>
            <div className="simple-list-row"><strong>2.</strong><span>Edit the metadata before retrieval starts.</span></div>
            <div className="simple-list-row"><strong>3.</strong><span>Read similar bills, legal conflict, and stakeholder reports.</span></div>
            <div className="simple-list-row"><strong>4.</strong><span>Finish in the final versioned drafting workspace.</span></div>
          </div>
          <NextStepCard
            to="/bills/database"
            title="Open Bills Database"
            description="Inspect precedent before you draft."
            icon={FolderOpen}
          />
        </SectionFrame>
      </div>

      <SectionFrame
        eyebrow="Saved work"
        title="Resume a workspace"
        description="Open the bill directly at its saved page. The current stage is always preserved."
        icon={FolderOpen}
      >
        {projectsQuery.isLoading ? <div className="loading-line">Loading saved workspaces...</div> : null}
        {projectsQuery.data?.length ? (
          <div className="workspace-grid">
            <button type="button" className="project-card project-card-create" onClick={() => createProject.mutate()}>
              <div className="project-create-icon">
                <Plus size={26} />
              </div>
              <h3 className="project-card-title">New Bill</h3>
              <p className="project-card-description">Create a fresh legislative drafting workspace.</p>
            </button>
            {projectsQuery.data.map((project) => (
              <article key={project.project_id} className="project-card">
                <div className="project-card-top">
                  <StatusBadge>{project.status}</StatusBadge>
                  <StatusBadge tone="info">{project.jurisdiction_name}</StatusBadge>
                </div>
                <h3 className="project-card-title">{project.title}</h3>
                <p className="project-card-description">
                  Current page: <strong>{formatStageLabel(project.current_stage)}</strong>
                </p>
                <div className="project-card-meta">
                  <span>Updated {new Date(project.updated_at).toLocaleString()}</span>
                </div>
                <Link to={getProjectPath(project.project_id, project.current_stage)} className="button button-primary">
                  Open Page ({formatResumeLabel(project.current_stage)})
                </Link>
              </article>
            ))}
          </div>
        ) : (
          !projectsQuery.isLoading && (
            <EmptyState
              icon={FolderOpen}
              title="No workspaces yet"
              description="Create your first bill workspace above to begin the guided drafting flow."
            />
          )
        )}
      </SectionFrame>
    </div>
  );
}

function getProjectPath(projectId: string, stageKey: string) {
  if (stageKey === 'editor') {
    return `/projects/${projectId}/editor`;
  }

  return `/projects/${projectId}/${stageKey}`;
}

function formatResumeLabel(stageKey: string) {
  switch (stageKey) {
    case 'similar-bills':
      return 'Fetch Similar Bills';
    case 'metadata':
      return 'Generate Metadata';
    default:
      return formatStageLabel(stageKey);
  }
}
