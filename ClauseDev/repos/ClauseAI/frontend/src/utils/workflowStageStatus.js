import {
    STEP_PATHS,
    STAGE_BAR_ITEMS,
    STAGE_ROUTE_BY_KEY,
    normalizeStepPath
} from '../workflow/definitions';

export { STAGE_BAR_ITEMS, STAGE_ROUTE_BY_KEY };

const hasValue = (value) => value != null && String(value).trim() !== '';

const getTrackingStatus = (workflow, key) => workflow?.requestTracking?.[key]?.status || null;
const getMetadataField = (workflow, lower, upper) => {
    return workflow?.metadata?.[lower] ?? workflow?.metadata?.[upper] ?? '';
};

const hasExtraction = (workflow) => hasValue(workflow?.extraction?.editedText || workflow?.billText);
const hasMetadata = (workflow) => (
    hasValue(getMetadataField(workflow, 'title', 'Title')) &&
    hasValue(getMetadataField(workflow, 'description', 'Description'))
);
const hasSimilarity = (workflow) => Array.isArray(workflow?.similarBills) && workflow.similarBills.length > 0;
const hasLoader = (workflow) => (
    Array.isArray(workflow?.similarBillsLoaded?.data?.Passed_Bills) &&
    Array.isArray(workflow?.similarBillsLoaded?.data?.Failed_Bills)
);
const hasBillAnalysis = (workflow) => hasValue(workflow?.billAnalysis?.report);
const hasLegal = (workflow) => Boolean(workflow?.legalAnalysis?.structuredData || hasValue(workflow?.legalAnalysis?.report));
const hasStakeholder = (workflow) => Boolean(
    workflow?.stakeholderAnalysis?.structuredData || hasValue(workflow?.stakeholderAnalysis?.report)
);

export const getStageKeyForPath = (path = '') => {
    const normalized = normalizeStepPath(path || '');
    if (!normalized) return 'extraction';
    if (normalized.startsWith('/final')) return 'final';
    if (normalized.startsWith('/stakeholder-analysis')) return 'stakeholderAnalysis';
    if (normalized.startsWith('/legal-analysis')) return 'conflictAnalysis';
    if (normalized.startsWith('/bill-analysis')) return 'billAnalysis';
    if (normalized.startsWith('/similar-bills-loader')) return 'loader';
    if (normalized.startsWith('/similar-bills')) return 'similarity';
    if (normalized.startsWith('/metadata')) return 'metadata';
    if (normalized.startsWith('/extraction')) return 'extraction';
    return 'extraction';
};

const resolvePrerequisiteRoute = (workflow, route) => {
    const extractionReady = hasExtraction(workflow);
    const metadataReady = hasMetadata(workflow);
    const similarityReady = hasSimilarity(workflow);
    const loaderReady = hasLoader(workflow);
    const billAnalysisReady = hasBillAnalysis(workflow);
    const legalReady = hasLegal(workflow);
    const stakeholderReady = hasStakeholder(workflow);

    if (route === STEP_PATHS.EXTRACTION_OUTPUT) {
        return extractionReady ? null : STEP_PATHS.EXTRACTION_INPUT;
    }

    if (route === STEP_PATHS.METADATA) {
        if (!extractionReady) return STEP_PATHS.EXTRACTION_INPUT;
        return null;
    }

    if (route === STEP_PATHS.SIMILAR_BILLS) {
        if (!extractionReady) return STEP_PATHS.EXTRACTION_INPUT;
        if (!metadataReady) return STEP_PATHS.METADATA;
        return null;
    }

    if (route === STEP_PATHS.SIMILAR_BILLS_LOADER) {
        if (!extractionReady) return STEP_PATHS.EXTRACTION_INPUT;
        if (!metadataReady) return STEP_PATHS.METADATA;
        if (!similarityReady) return STEP_PATHS.SIMILAR_BILLS;
        return null;
    }

    if (route === STEP_PATHS.BILL_ANALYSIS_REPORT) {
        if (!extractionReady) return STEP_PATHS.EXTRACTION_INPUT;
        if (!metadataReady) return STEP_PATHS.METADATA;
        if (!similarityReady) return STEP_PATHS.SIMILAR_BILLS;
        if (!loaderReady) return STEP_PATHS.SIMILAR_BILLS_LOADER;
        return null;
    }

    if (route === STEP_PATHS.LEGAL_ANALYSIS_REPORT) {
        if (!extractionReady) return STEP_PATHS.EXTRACTION_INPUT;
        if (!metadataReady) return STEP_PATHS.METADATA;
        if (!similarityReady) return STEP_PATHS.SIMILAR_BILLS;
        if (!loaderReady) return STEP_PATHS.SIMILAR_BILLS_LOADER;
        if (!billAnalysisReady) return STEP_PATHS.BILL_ANALYSIS_REPORT;
        return null;
    }

    if (route === STEP_PATHS.STAKEHOLDER_REPORT) {
        if (!extractionReady) return STEP_PATHS.EXTRACTION_INPUT;
        if (!metadataReady) return STEP_PATHS.METADATA;
        if (!similarityReady) return STEP_PATHS.SIMILAR_BILLS;
        if (!loaderReady) return STEP_PATHS.SIMILAR_BILLS_LOADER;
        if (!billAnalysisReady) return STEP_PATHS.BILL_ANALYSIS_REPORT;
        if (!legalReady) return STEP_PATHS.LEGAL_ANALYSIS_REPORT;
        return null;
    }

    if (route === STEP_PATHS.FINAL_REPORT) {
        if (!extractionReady) return STEP_PATHS.EXTRACTION_INPUT;
        if (!metadataReady) return STEP_PATHS.METADATA;
        if (!similarityReady) return STEP_PATHS.SIMILAR_BILLS;
        if (!loaderReady) return STEP_PATHS.SIMILAR_BILLS_LOADER;
        if (!billAnalysisReady) return STEP_PATHS.BILL_ANALYSIS_REPORT;
        if (!legalReady) return STEP_PATHS.LEGAL_ANALYSIS_REPORT;
        if (!stakeholderReady) return STEP_PATHS.STAKEHOLDER_REPORT;
        return null;
    }

    return null;
};

export const resolveWorkflowStageRoute = (workflow, stageKey) => {
    const route = STAGE_ROUTE_BY_KEY[stageKey] || STEP_PATHS.EXTRACTION_INPUT;
    const fallback = resolvePrerequisiteRoute(workflow, route);
    return fallback || route;
};

export const isStageRouteAccessible = (workflow, stageKey) => {
    const route = STAGE_ROUTE_BY_KEY[stageKey] || STEP_PATHS.EXTRACTION_INPUT;
    const fallback = resolvePrerequisiteRoute(workflow, route);
    return !fallback;
};

export const getStageNavigationState = (workflow, stageKey) => {
    const route = STAGE_ROUTE_BY_KEY[stageKey] || STEP_PATHS.EXTRACTION_INPUT;
    const fallback = resolvePrerequisiteRoute(workflow, route);
    return {
        route: fallback || route,
        locked: Boolean(fallback)
    };
};

export const getStageStatus = (workflow, key) => {
    if (!workflow) return 'idle';

    const status = key === 'final'
        ? null
        : getTrackingStatus(workflow, key);

    if (status === 'running') return 'running';
    if (status === 'failed') return 'failed';

    if (key === 'extraction') return hasExtraction(workflow) ? 'completed' : 'idle';
    if (key === 'metadata') {
        return hasValue(
            getMetadataField(workflow, 'title', 'Title') ||
            getMetadataField(workflow, 'description', 'Description') ||
            getMetadataField(workflow, 'summary', 'Summary')
        ) ? 'completed' : 'idle';
    }
    if (key === 'similarity') return hasSimilarity(workflow) ? 'completed' : 'idle';
    if (key === 'loader') return hasLoader(workflow) ? 'completed' : 'idle';
    if (key === 'billAnalysis') return hasBillAnalysis(workflow) ? 'completed' : 'idle';
    if (key === 'conflictAnalysis') return hasLegal(workflow) ? 'completed' : 'idle';
    if (key === 'stakeholderAnalysis') return hasStakeholder(workflow) ? 'completed' : 'idle';
    if (key === 'final') return workflow?.finalReport?.generatedAt ? 'completed' : 'idle';

    return 'idle';
};
