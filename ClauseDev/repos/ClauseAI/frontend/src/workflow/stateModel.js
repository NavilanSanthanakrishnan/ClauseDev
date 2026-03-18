const clone = (value) => {
    if (!value || typeof value !== 'object') return value;
    return JSON.parse(JSON.stringify(value));
};

const mergeDeep = (target, source) => {
    if (!source || typeof source !== 'object') return target;
    Object.keys(source).forEach((key) => {
        const sourceValue = source[key];
        if (Array.isArray(sourceValue)) {
            target[key] = sourceValue;
            return;
        }
        if (sourceValue && typeof sourceValue === 'object') {
            if (!target[key] || typeof target[key] !== 'object') {
                target[key] = {};
            }
            target[key] = mergeDeep(target[key], sourceValue);
            return;
        }
        target[key] = sourceValue;
    });
    return target;
};

const defaultAnalysisDomain = {
    report: '',
    structuredData: null,
    improvements: [],
    validImprovementIndices: [],
    invalidImprovements: [],
    validationSummary: null,
    warning: null,
    directImprovements: [],
    processingTime: null
};

export const defaultCanonicalWorkflow = {
    currentStep: '/',
    mockReplay: false,
    document: {
        billText: '',
        fixApplicationBaseText: '',
        extraction: {
            originalText: '',
            editedText: '',
            stats: null,
            fileName: '',
            fileSize: 0,
            fileType: ''
        },
        metadata: {
            title: '',
            description: '',
            summary: '',
            processingTime: null
        },
        similarBills: [],
        similarBillsStats: {
            total: 0,
            passed: 0,
            failed: 0
        },
        similarBillsLoaded: {
            data: null,
            expandedBillIds: [],
            selectedBillId: null
        }
    },
    analysis: {
        bill: {
            ...clone(defaultAnalysisDomain),
            structuredData: null
        },
        legal: {
            ...clone(defaultAnalysisDomain),
            directImprovements: []
        },
        stakeholder: {
            ...clone(defaultAnalysisDomain),
            directImprovements: []
        }
    },
    fixes: {
        bill: {
            billText: '',
            history: [],
            appliedOrder: [],
            appliedSet: [],
            lastApplied: null,
            itemErrors: {}
        },
        legal: {
            billText: '',
            history: [],
            appliedOrder: [],
            appliedSet: [],
            lastApplied: null,
            itemErrors: {}
        },
        stakeholder: {
            billText: '',
            history: [],
            appliedOrder: [],
            appliedSet: [],
            lastApplied: null,
            itemErrors: {}
        }
    },
    finalReport: {
        generatedAt: null
    },
    requests: {
        extraction: { requestId: null, status: null },
        metadata: { requestId: null, status: null },
        similarity: { requestId: null, status: null },
        loader: { requestId: null, status: null },
        billAnalysis: { requestId: null, status: null },
        conflictAnalysis: { requestId: null, status: null },
        stakeholderAnalysis: { requestId: null, status: null }
    }
};

export const legacyToCanonical = (legacyPayload = {}) => {
    const legacy = clone(legacyPayload) || {};

    const canonical = clone(defaultCanonicalWorkflow);

    canonical.currentStep = legacy.currentStep || canonical.currentStep;
    canonical.mockReplay = Boolean(legacy.mockReplay);

    canonical.document.billText = legacy.billText || '';
    canonical.document.fixApplicationBaseText = legacy.fixApplicationBaseText || '';
    canonical.document.extraction = mergeDeep(clone(defaultCanonicalWorkflow.document.extraction), legacy.extraction || {});
    const normalizedLegacyMetadata = {
        ...(legacy.metadata || {}),
        title: legacy.metadata?.title ?? legacy.metadata?.Title ?? '',
        description: legacy.metadata?.description ?? legacy.metadata?.Description ?? '',
        summary: legacy.metadata?.summary ?? legacy.metadata?.Summary ?? ''
    };
    canonical.document.metadata = mergeDeep(
        clone(defaultCanonicalWorkflow.document.metadata),
        normalizedLegacyMetadata
    );
    canonical.document.similarBills = Array.isArray(legacy.similarBills) ? legacy.similarBills : [];
    canonical.document.similarBillsStats = mergeDeep(clone(defaultCanonicalWorkflow.document.similarBillsStats), legacy.similarBillsStats || {});
    canonical.document.similarBillsLoaded = mergeDeep(clone(defaultCanonicalWorkflow.document.similarBillsLoaded), legacy.similarBillsLoaded || {});

    canonical.analysis.bill = mergeDeep(clone(defaultCanonicalWorkflow.analysis.bill), legacy.billAnalysis || {});
    canonical.analysis.legal = mergeDeep(clone(defaultCanonicalWorkflow.analysis.legal), legacy.legalAnalysis || {});
    canonical.analysis.stakeholder = mergeDeep(clone(defaultCanonicalWorkflow.analysis.stakeholder), legacy.stakeholderAnalysis || {});

    canonical.fixes.bill = mergeDeep(clone(defaultCanonicalWorkflow.fixes.bill), legacy.billFixes || {});
    canonical.fixes.legal = mergeDeep(clone(defaultCanonicalWorkflow.fixes.legal), legacy.legalFixes || {});
    canonical.fixes.stakeholder = mergeDeep(clone(defaultCanonicalWorkflow.fixes.stakeholder), legacy.stakeholderFixes || {});

    canonical.finalReport = mergeDeep(clone(defaultCanonicalWorkflow.finalReport), legacy.finalReport || {});
    canonical.requests = mergeDeep(clone(defaultCanonicalWorkflow.requests), legacy.requestTracking || {});

    return canonical;
};

export const canonicalToLegacy = (canonicalPayload = {}) => {
    const canonical = mergeDeep(clone(defaultCanonicalWorkflow), clone(canonicalPayload || {}));

    return {
        currentStep: canonical.currentStep,
        mockReplay: canonical.mockReplay,
        billText: canonical.document.billText,
        fixApplicationBaseText: canonical.document.fixApplicationBaseText,
        extraction: canonical.document.extraction,
        metadata: canonical.document.metadata,
        similarBills: canonical.document.similarBills,
        similarBillsStats: canonical.document.similarBillsStats,
        similarBillsLoaded: canonical.document.similarBillsLoaded,
        billAnalysis: canonical.analysis.bill,
        billFixes: canonical.fixes.bill,
        legalAnalysis: canonical.analysis.legal,
        legalFixes: canonical.fixes.legal,
        stakeholderAnalysis: canonical.analysis.stakeholder,
        stakeholderFixes: canonical.fixes.stakeholder,
        finalReport: canonical.finalReport,
        requestTracking: canonical.requests
    };
};

export const fromServerWorkflow = (legacyPayload = {}) => {
    return legacyToCanonical(legacyPayload);
};

export const toServerWorkflow = (canonicalPayload = {}) => {
    return canonicalToLegacy(canonicalPayload);
};

export const createDefaultCanonicalWorkflow = () => clone(defaultCanonicalWorkflow);
export const createDefaultLegacyWorkflow = () => canonicalToLegacy(defaultCanonicalWorkflow);

export const canonicalMerge = (base, patch) => {
    return mergeDeep(clone(base || defaultCanonicalWorkflow), clone(patch || {}));
};

export const legacyMerge = (baseLegacy, patchLegacy) => {
    const baseCanonical = legacyToCanonical(baseLegacy || {});
    const patchCanonical = legacyToCanonical(patchLegacy || {});
    return canonicalToLegacy(canonicalMerge(baseCanonical, patchCanonical));
};
