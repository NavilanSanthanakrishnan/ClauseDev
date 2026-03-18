export type CoreStageKey =
  | 'upload'
  | 'extraction'
  | 'metadata'
  | 'similar-bills'
  | 'legal'
  | 'stakeholders'
  | 'editor';

export type WorkflowPageKey =
  | 'upload'
  | 'extraction'
  | 'metadata'
  | 'similar-bills'
  | 'similar-bills-report'
  | 'similar-bills-fixes'
  | 'legal'
  | 'legal-report'
  | 'legal-fixes'
  | 'stakeholders'
  | 'stakeholders-report'
  | 'stakeholders-fixes'
  | 'editor';

export type AnalysisStageKey = Extract<CoreStageKey, 'similar-bills' | 'legal' | 'stakeholders'>;

export type WorkflowPageDefinition = {
  key: WorkflowPageKey;
  coreStage: CoreStageKey;
  navLabel: string;
  title: string;
  summary: string;
  buildPath: (projectId: string) => string;
};

export const CORE_STAGE_ORDER: CoreStageKey[] = [
  'upload',
  'extraction',
  'metadata',
  'similar-bills',
  'legal',
  'stakeholders',
  'editor',
];

export const workflowPageDefinitions: WorkflowPageDefinition[] = [
  {
    key: 'upload',
    coreStage: 'upload',
    navLabel: 'Upload Bill',
    title: 'Upload the bill file',
    summary: 'Start by adding the source bill as a PDF, DOCX, or TXT file.',
    buildPath: (projectId) => `/projects/${projectId}/upload`,
  },
  {
    key: 'extraction',
    coreStage: 'extraction',
    navLabel: 'Review Text',
    title: 'Check the extracted text',
    summary: 'Make sure the bill text looks correct before you generate metadata.',
    buildPath: (projectId) => `/projects/${projectId}/extraction`,
  },
  {
    key: 'metadata',
    coreStage: 'metadata',
    navLabel: 'Metadata',
    title: 'Generate the bill metadata',
    summary: 'Create and edit the metadata the later stages rely on.',
    buildPath: (projectId) => `/projects/${projectId}/metadata`,
  },
  {
    key: 'similar-bills',
    coreStage: 'similar-bills',
    navLabel: 'Similar Bills Search',
    title: 'Run the similar bills search',
    summary: 'Retrieve similar bills, inspect the matches, and open the analysis report.',
    buildPath: (projectId) => `/projects/${projectId}/similar-bills`,
  },
  {
    key: 'similar-bills-report',
    coreStage: 'similar-bills',
    navLabel: 'Similar Bills Report',
    title: 'Read the similar bills report',
    summary: 'Review the precedent analysis and its general drafting guidance.',
    buildPath: (projectId) => `/projects/${projectId}/similar-bills/report`,
  },
  {
    key: 'similar-bills-fixes',
    coreStage: 'similar-bills',
    navLabel: 'Similar Bills Guidance',
    title: 'Review the similar bills guidance',
    summary: 'Inspect the general drafting guidance pulled from the precedent search.',
    buildPath: (projectId) => `/projects/${projectId}/similar-bills/fixes`,
  },
  {
    key: 'legal',
    coreStage: 'legal',
    navLabel: 'Legal Conflict',
    title: 'Run the legal conflict check',
    summary: 'Identify conflicting laws and produce the legal report before editing.',
    buildPath: (projectId) => `/projects/${projectId}/legal`,
  },
  {
    key: 'legal-report',
    coreStage: 'legal',
    navLabel: 'Legal Report',
    title: 'Read the legal report',
    summary: 'Review the saved legal analysis and its general drafting guidance.',
    buildPath: (projectId) => `/projects/${projectId}/legal/report`,
  },
  {
    key: 'legal-fixes',
    coreStage: 'legal',
    navLabel: 'Legal Guidance',
    title: 'Review the legal guidance',
    summary: 'Inspect the legal drafting guidance with its reasons.',
    buildPath: (projectId) => `/projects/${projectId}/legal/fixes`,
  },
  {
    key: 'stakeholders',
    coreStage: 'stakeholders',
    navLabel: 'Stakeholder Analysis',
    title: 'Run the stakeholder check',
    summary: 'Identify likely supporters and opponents before the final editor.',
    buildPath: (projectId) => `/projects/${projectId}/stakeholders`,
  },
  {
    key: 'stakeholders-report',
    coreStage: 'stakeholders',
    navLabel: 'Stakeholder Report',
    title: 'Read the stakeholder report',
    summary: 'Review the stakeholder analysis and its general drafting guidance.',
    buildPath: (projectId) => `/projects/${projectId}/stakeholders/report`,
  },
  {
    key: 'stakeholders-fixes',
    coreStage: 'stakeholders',
    navLabel: 'Stakeholder Guidance',
    title: 'Review the stakeholder guidance',
    summary: 'See the saved stakeholder guidance before you open the editor.',
    buildPath: (projectId) => `/projects/${projectId}/stakeholders/fixes`,
  },
  {
    key: 'editor',
    coreStage: 'editor',
    navLabel: 'Draft Editor',
    title: 'Finish the draft in the editor',
    summary: 'Run the final Codex drafting loop, approve changes, and export the latest draft.',
    buildPath: (projectId) => `/projects/${projectId}/editor`,
  },
];

export function getWorkflowPages(projectId: string) {
  return workflowPageDefinitions.map((page) => ({
    ...page,
    to: page.buildPath(projectId),
  }));
}

export function getWorkflowPageKeyFromPath(pathname: string): WorkflowPageKey {
  const segments = pathname.split('/').filter(Boolean);
  const leaf = segments.at(-1);
  const parent = segments.at(-2);

  if (leaf === 'report' || leaf === 'fixes') {
    return `${parent}-${leaf}` as WorkflowPageKey;
  }

  return (leaf ?? 'upload') as WorkflowPageKey;
}

export function formatStageLabel(stageKey: string) {
  return stageKey
    .split('-')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
}

export function getCoreStageSummary(stageKey: CoreStageKey) {
  return (
    workflowPageDefinitions.find((page) => page.key === stageKey)?.summary
    ?? formatStageLabel(stageKey)
  );
}
