import { extractOptimizations } from '../utils/fixChangeApplicator';
import { normalizeFixClassificationPayload } from '../utils/fixMapping';
import { STEP_PATHS } from './definitions';

export const FIXES_CONFIG = {
    bill: {
        workflowKey: 'billFixes',
        currentStep: STEP_PATHS.BILL_ANALYSIS_FIXES,
        fallbackRoute: STEP_PATHS.BILL_ANALYSIS_REPORT,
        continueRoute: STEP_PATHS.LEGAL_ANALYSIS_REPORT,
        title: 'Bill Analysis Fixes',
        subtitle: 'Apply or revert suggested bill edits with inline diff view.',
        improvementsLabel: 'Suggested Improvements',
        continueLabel: 'Continue to Legal Analysis',
        applyToast: (idx) => `Applied improvement ${idx + 1}`,
        revertToast: (idx) => `Reverted improvement ${idx + 1}`,
        applyErrorFallback: 'Failed to apply improvement',
        revertErrorFallback: 'Failed to revert improvement',
        classify: (workflow) => normalizeFixClassificationPayload(
            workflow.billAnalysis,
            workflow.billAnalysis?.directImprovements || []
        ),
        titleResolver: (item, idx) => item?.metadata?.short_explanation || item?.short_explanation || item?.title || item?.metadata?.section || `Improvement ${idx + 1}`,
        rationaleResolver: (item) => item?.metadata?.explanation || item?.explanation || item?.rationale || 'No rationale provided.',
        sectionResolver: (item, idx) => item?.metadata?.section || `Improvement ${idx + 1}`,
        invalidTitleResolver: (item, idx) => item?.metadata?.short_explanation || item?.short_explanation || item?.title || `Invalid Patch ${idx + 1}`
    },
    legal: {
        workflowKey: 'legalFixes',
        currentStep: STEP_PATHS.LEGAL_ANALYSIS_FIXES,
        fallbackRoute: STEP_PATHS.LEGAL_ANALYSIS_REPORT,
        continueRoute: STEP_PATHS.STAKEHOLDER_REPORT,
        title: 'Legal Analysis Fixes',
        subtitle: 'Apply or revert legal remediations with inline diff view.',
        improvementsLabel: 'Legal Improvements',
        continueLabel: 'Continue to Stakeholder Analysis',
        applyToast: (idx) => `Applied legal improvement ${idx + 1}`,
        revertToast: (idx) => `Reverted legal improvement ${idx + 1}`,
        applyErrorFallback: 'Failed to apply legal improvement',
        revertErrorFallback: 'Failed to revert legal improvement',
        classify: (workflow) => normalizeFixClassificationPayload(
            workflow.legalAnalysis,
            workflow.legalAnalysis?.structuredData?.legal_improvements || []
        ),
        titleResolver: (item, idx) => item?.short_explanation || item?.improvement_type || item?.addresses_issue || item?.title || `Improvement ${idx + 1}`,
        rationaleResolver: (item) => item?.explanation || item?.rationale || 'No rationale provided.',
        sectionResolver: (item, idx) => item?.improvement_type || `Improvement ${idx + 1}`,
        invalidTitleResolver: (item, idx) => item?.short_explanation || item?.improvement_type || item?.addresses_issue || `Invalid Patch ${idx + 1}`
    },
    stakeholder: {
        workflowKey: 'stakeholderFixes',
        currentStep: STEP_PATHS.STAKEHOLDER_FIXES,
        fallbackRoute: STEP_PATHS.STAKEHOLDER_REPORT,
        continueRoute: STEP_PATHS.FINAL_REPORT,
        title: 'Stakeholder Analysis Fixes',
        subtitle: 'Apply or revert stakeholder-focused language optimizations with inline diff view.',
        improvementsLabel: 'Stakeholder Optimizations',
        continueLabel: 'Continue to Final Report',
        applyToast: (idx) => `Applied stakeholder improvement ${idx + 1}`,
        revertToast: (idx) => `Reverted stakeholder improvement ${idx + 1}`,
        applyErrorFallback: 'Failed to apply stakeholder improvement',
        revertErrorFallback: 'Failed to revert stakeholder improvement',
        classify: (workflow) => normalizeFixClassificationPayload(
            workflow.stakeholderAnalysis,
            extractOptimizations(workflow.stakeholderAnalysis?.structuredData)
        ),
        titleResolver: (item, idx) => item?.short_explanation || item?.summary || item?.title || item?.optimization_strategy || `Optimization ${idx + 1}`,
        rationaleResolver: (item) => item?.explanation || item?.description || item?.rationale || 'No rationale provided.',
        sectionResolver: (item, idx) => item?.optimization_strategy || `Optimization ${idx + 1}`,
        invalidTitleResolver: (item, idx) => item?.short_explanation || item?.summary || item?.title || item?.optimization_strategy || `Invalid Patch ${idx + 1}`
    }
};
