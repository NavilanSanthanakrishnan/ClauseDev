export const STEP_PATHS = {
    HOME: '/',
    LOGIN: '/login',
    API_CHECK: '/api-check',
    EXTRACTION_INPUT: '/extraction-input',
    EXTRACTION_OUTPUT: '/extraction-output',
    DOCUMENT: '/document',
    METADATA: '/metadata',
    SIMILAR_BILLS: '/similar-bills',
    SIMILAR_BILLS_LOADER: '/similar-bills-loader',
    BILL_ANALYSIS_REPORT: '/bill-analysis-report',
    BILL_ANALYSIS_FIXES: '/bill-analysis-fixes',
    LEGAL_ANALYSIS_REPORT: '/legal-analysis-report',
    LEGAL_ANALYSIS_FIXES: '/legal-analysis-fixes',
    STAKEHOLDER_REPORT: '/stakeholder-analysis-report',
    STAKEHOLDER_FIXES: '/stakeholder-analysis-fixes',
    BILL_INSPECT: '/bill-inspect',
    FINAL_REPORT: '/final-report',
    FINAL_EDITING: '/final-editing'
};

export const LEGACY_STEP_REDIRECTS = {
    [STEP_PATHS.DOCUMENT]: STEP_PATHS.EXTRACTION_OUTPUT
};

export const normalizeStepPath = (path) => {
    if (!path || typeof path !== 'string') return STEP_PATHS.HOME;
    return LEGACY_STEP_REDIRECTS[path] || path;
};

export const STAGE_BAR_ITEMS = [
    { key: 'extraction', label: 'Extraction', route: STEP_PATHS.EXTRACTION_OUTPUT },
    { key: 'metadata', label: 'Metadata', route: STEP_PATHS.METADATA },
    { key: 'similarity', label: 'Similarity', route: STEP_PATHS.SIMILAR_BILLS },
    { key: 'loader', label: 'Loader', route: STEP_PATHS.SIMILAR_BILLS_LOADER },
    { key: 'billAnalysis', label: 'Bill Analysis', route: STEP_PATHS.BILL_ANALYSIS_REPORT },
    { key: 'conflictAnalysis', label: 'Legal', route: STEP_PATHS.LEGAL_ANALYSIS_REPORT },
    { key: 'stakeholderAnalysis', label: 'Stakeholder', route: STEP_PATHS.STAKEHOLDER_REPORT },
    { key: 'final', label: 'Final', route: STEP_PATHS.FINAL_REPORT }
];

export const STAGE_ROUTE_BY_KEY = Object.fromEntries(
    STAGE_BAR_ITEMS.map((item) => [item.key, item.route])
);

export const NEXT_STEP_BY_PATH = {
    [STEP_PATHS.EXTRACTION_INPUT]: STEP_PATHS.EXTRACTION_OUTPUT,
    [STEP_PATHS.EXTRACTION_OUTPUT]: STEP_PATHS.METADATA,
    [STEP_PATHS.METADATA]: STEP_PATHS.SIMILAR_BILLS,
    [STEP_PATHS.SIMILAR_BILLS]: STEP_PATHS.SIMILAR_BILLS_LOADER,
    [STEP_PATHS.SIMILAR_BILLS_LOADER]: STEP_PATHS.BILL_ANALYSIS_REPORT,
    [STEP_PATHS.BILL_ANALYSIS_REPORT]: STEP_PATHS.BILL_ANALYSIS_FIXES,
    [STEP_PATHS.BILL_ANALYSIS_FIXES]: STEP_PATHS.LEGAL_ANALYSIS_REPORT,
    [STEP_PATHS.LEGAL_ANALYSIS_REPORT]: STEP_PATHS.LEGAL_ANALYSIS_FIXES,
    [STEP_PATHS.LEGAL_ANALYSIS_FIXES]: STEP_PATHS.STAKEHOLDER_REPORT,
    [STEP_PATHS.STAKEHOLDER_REPORT]: STEP_PATHS.STAKEHOLDER_FIXES,
    [STEP_PATHS.STAKEHOLDER_FIXES]: STEP_PATHS.FINAL_REPORT,
    [STEP_PATHS.FINAL_REPORT]: STEP_PATHS.FINAL_EDITING
};

export const getNextStepPath = (path) => {
    const normalized = normalizeStepPath(path);
    return NEXT_STEP_BY_PATH[normalized] || normalized;
};
