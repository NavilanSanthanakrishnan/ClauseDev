import {
  Eye,
  FilePenLine,
  FileSearch,
  FileText,
  LibraryBig,
  ScanText,
  ShieldAlert,
  Upload,
  Users,
  Wrench,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';

import { type WorkflowPageKey, getWorkflowPages } from '../lib/stages';

const workflowIcons: Record<WorkflowPageKey, LucideIcon> = {
  upload: Upload,
  extraction: ScanText,
  metadata: Eye,
  'similar-bills': LibraryBig,
  'similar-bills-report': FileText,
  'similar-bills-fixes': Wrench,
  legal: ShieldAlert,
  'legal-report': FileText,
  'legal-fixes': Wrench,
  stakeholders: Users,
  'stakeholders-report': FileSearch,
  'stakeholders-fixes': Wrench,
  editor: FilePenLine,
};

type WorkflowStageNavProps = {
  projectId: string;
  currentPage: WorkflowPageKey;
};

export function WorkflowStageNav({ projectId, currentPage }: WorkflowStageNavProps) {
  return (
    <nav className="workflow-nav" aria-label="Workflow pages">
      {getWorkflowPages(projectId).map((page, index) => {
        const Icon = workflowIcons[page.key];

        return (
          <Link key={page.key} to={page.to} className={`workflow-link${page.key === currentPage ? ' active' : ''}`}>
            <div className="workflow-link-left">
              <div className="workflow-link-icon">
                <Icon size={16} />
              </div>
              <div>
                <div className="workflow-link-step">Page {String(index + 1).padStart(2, '0')}</div>
                <div className="workflow-link-title">{page.navLabel}</div>
              </div>
            </div>
            <span className="workflow-link-state">{page.key === currentPage ? 'Open' : 'Go'}</span>
          </Link>
        );
      })}
    </nav>
  );
}
