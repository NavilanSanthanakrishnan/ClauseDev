import { createLogger } from './logger';
import { API_CONFIG } from '../config/api';
import { getAccessToken } from '../lib/supabaseClient';
import {
    getAppliedSetsFromWorkflow,
    getFixPoolsFromWorkflow,
    recomputeBillTextFromAppliedSets
} from './fixApplication';
import {
    canonicalToLegacy,
    createDefaultCanonicalWorkflow,
    createDefaultLegacyWorkflow,
    fromServerWorkflow,
    legacyToCanonical,
    toServerWorkflow
} from '../workflow/stateModel';
import { STEP_PATHS, normalizeStepPath } from '../workflow/definitions';

const logger = createLogger('workflowStorage');

const STORAGE_KEY = 'clauseai.workflow.v1';
export const WORKFLOW_STORAGE_KEY = STORAGE_KEY;
export const WORKFLOW_UPDATED_EVENT = 'clauseai:workflow-updated';
export const WORKFLOW_HYDRATED_EVENT = 'clauseai:workflow-hydrated';

const STORAGE_META_KEY = `${STORAGE_KEY}.meta`;
const HISTORY_LIMIT = 30;
const PERSIST_DEBOUNCE_MS = 450;
const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30000;

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

const defaultWorkflow = createDefaultLegacyWorkflow();

let inMemoryWorkflowCanonical = createDefaultCanonicalWorkflow();
let inMemoryHistory = [];
let hydratePromise = null;
let persistTimer = null;
let persistInFlight = false;
let persistQueued = false;
let persistBackoffMs = 0;
let hydrationReady = false;
let hydrationStarted = false;
let shadowMeta = {
    updatedAt: 0,
    syncedAt: 0,
    lastSyncedHash: ''
};

const toLegacyWorkflow = () => canonicalToLegacy(inMemoryWorkflowCanonical);
const hashWorkflow = (workflow) => JSON.stringify(workflow || {});

const isBrowser = typeof window !== 'undefined';

const persistShadowMeta = () => {
    if (!isBrowser) return;
    try {
        window.localStorage.setItem(STORAGE_META_KEY, JSON.stringify(shadowMeta));
    } catch (error) {
        logger.warn('Failed to persist workflow shadow metadata', { error });
    }
};

const persistWorkflowShadow = () => {
    if (!isBrowser) return;
    try {
        const workflow = getWorkflow();
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(workflow));
        persistShadowMeta();
    } catch (error) {
        logger.warn('Failed to persist workflow shadow', { error });
    }
};

const hydrateFromLocalShadow = () => {
    if (!isBrowser) return;
    try {
        const workflowRaw = window.localStorage.getItem(STORAGE_KEY);
        if (workflowRaw) {
            const parsed = JSON.parse(workflowRaw);
            inMemoryWorkflowCanonical = legacyToCanonical(
                mergeDeep(clone(defaultWorkflow), parsed || {})
            );
        }
    } catch (error) {
        logger.warn('Failed to hydrate workflow from local shadow', { error });
    }

    try {
        const metaRaw = window.localStorage.getItem(STORAGE_META_KEY);
        if (metaRaw) {
            const parsedMeta = JSON.parse(metaRaw);
            shadowMeta = {
                updatedAt: Number(parsedMeta?.updatedAt) || 0,
                syncedAt: Number(parsedMeta?.syncedAt) || 0,
                lastSyncedHash: typeof parsedMeta?.lastSyncedHash === 'string' ? parsedMeta.lastSyncedHash : ''
            };
        }
    } catch (error) {
        logger.warn('Failed to hydrate workflow shadow metadata', { error });
    }
};

hydrateFromLocalShadow();

const dispatchWorkflowUpdated = (workflow) => {
    if (!isBrowser) return;
    window.dispatchEvent(
        new CustomEvent(WORKFLOW_UPDATED_EVENT, {
            detail: workflow
        })
    );
};

const dispatchWorkflowHydrated = () => {
    if (!isBrowser) return;
    window.dispatchEvent(
        new CustomEvent(WORKFLOW_HYDRATED_EVENT, {
            detail: { hydrated: true }
        })
    );
};

const markHydrationReady = () => {
    if (hydrationReady) return;
    hydrationReady = true;
    dispatchWorkflowHydrated();
};

const sendAuthenticatedRequest = async (endpoint, options = {}) => {
    const token = await getAccessToken().catch(() => null);
    if (!token) return null;
    const response = await fetch(`${API_CONFIG.BASE_URL}${endpoint}`, {
        method: options.method || 'GET',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            ...(options.headers || {})
        },
        body: options.body ? JSON.stringify(options.body) : undefined,
    });
    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const error = new Error(payload?.detail || payload?.message || `Request failed (${response.status})`);
        error.statusCode = response.status;
        throw error;
    }
    return response.json().catch(() => ({}));
};

const flushWorkflowPersist = async () => {
    if (persistInFlight) {
        persistQueued = true;
        return;
    }

    const current = toLegacyWorkflow();
    const currentHash = hashWorkflow(current);
    if (currentHash === shadowMeta.lastSyncedHash) {
        persistBackoffMs = 0;
        return;
    }

    persistInFlight = true;
    try {
        const response = await sendAuthenticatedRequest('/api/workflow/current', {
            method: 'PUT',
            body: {
                workflow: toServerWorkflow(inMemoryWorkflowCanonical),
                current_step: normalizeStepPath(current.currentStep || STEP_PATHS.HOME),
            },
        });
        if (response !== null) {
            const now = Date.now();
            shadowMeta.syncedAt = now;
            shadowMeta.updatedAt = Math.max(shadowMeta.updatedAt, now);
            shadowMeta.lastSyncedHash = currentHash;
            persistBackoffMs = 0;
            persistShadowMeta();
        }
    } catch (error) {
        const statusCode = Number(error?.statusCode) || 0;
        const shouldBackoff = statusCode === 429 || statusCode >= 500 || statusCode === 0;
        if (shouldBackoff) {
            persistBackoffMs = persistBackoffMs > 0
                ? Math.min(MAX_BACKOFF_MS, persistBackoffMs * 2)
                : INITIAL_BACKOFF_MS;
            scheduleWorkflowPersist(persistBackoffMs);
        } else {
            logger.warn('Failed to persist workflow to backend', { error });
        }
    } finally {
        persistInFlight = false;
        if (persistQueued) {
            persistQueued = false;
            scheduleWorkflowPersist(PERSIST_DEBOUNCE_MS);
        }
    }
};

const scheduleWorkflowPersist = (delayMs = PERSIST_DEBOUNCE_MS) => {
    if (persistTimer) clearTimeout(persistTimer);
    persistTimer = setTimeout(() => {
        persistTimer = null;
        flushWorkflowPersist();
    }, Math.max(0, delayMs));
};

export const hydrateWorkflowFromServer = async () => {
    if (hydratePromise) return hydratePromise;
    hydrationStarted = true;
    hydratePromise = (async () => {
        try {
            const [workflowPayload, historyPayload] = await Promise.all([
                sendAuthenticatedRequest('/api/workflow/current', { method: 'GET' }),
                sendAuthenticatedRequest('/api/workflow/history', { method: 'GET' }),
            ]);

            const localWorkflow = getWorkflow();
            const localHash = hashWorkflow(localWorkflow);
            const hasUnsyncedLocal = shadowMeta.updatedAt > shadowMeta.syncedAt;

            if (workflowPayload?.workflow) {
                const remoteCanonical = fromServerWorkflow(workflowPayload.workflow);
                const remoteLegacy = canonicalToLegacy(remoteCanonical);
                const remoteHash = hashWorkflow(remoteLegacy);
                const shouldKeepLocal = hasUnsyncedLocal && localHash !== remoteHash;

                if (shouldKeepLocal) {
                    logger.info('Preserving newer local workflow shadow over server payload');
                    scheduleWorkflowPersist(PERSIST_DEBOUNCE_MS);
                } else {
                    inMemoryWorkflowCanonical = remoteCanonical;
                    const now = Date.now();
                    shadowMeta.updatedAt = now;
                    shadowMeta.syncedAt = now;
                    shadowMeta.lastSyncedHash = remoteHash;
                    persistWorkflowShadow();
                }
            }

            if (Array.isArray(historyPayload?.items)) {
                inMemoryHistory = historyPayload.items;
            }

            dispatchWorkflowUpdated(getWorkflow());
            return getWorkflow();
        } catch (error) {
            logger.warn('Failed to hydrate workflow from backend', { error });
            return getWorkflow();
        } finally {
            hydratePromise = null;
            markHydrationReady();
        }
    })();
    return hydratePromise;
};

export const isWorkflowHydrated = () => hydrationReady;

export const waitForWorkflowHydration = (timeoutMs = 8000) => {
    if (hydrationReady) return Promise.resolve(true);
    if (!hydrationStarted) {
        hydrateWorkflowFromServer();
    }
    if (!isBrowser) return Promise.resolve(false);

    return new Promise((resolve) => {
        let resolved = false;
        const finish = (value) => {
            if (resolved) return;
            resolved = true;
            window.removeEventListener(WORKFLOW_HYDRATED_EVENT, onHydrated);
            clearTimeout(timeoutId);
            resolve(value);
        };
        const onHydrated = () => finish(true);
        const timeoutId = setTimeout(() => finish(false), Math.max(1000, timeoutMs));
        window.addEventListener(WORKFLOW_HYDRATED_EVENT, onHydrated);
    });
};

const getHistory = () => {
    return Array.isArray(inMemoryHistory) ? inMemoryHistory : [];
};

const setHistory = (entries) => {
    const list = Array.isArray(entries) ? entries : [];
    inMemoryHistory = list;
    return list;
};

export const getWorkflow = () => {
    return mergeDeep(clone(defaultWorkflow), clone(toLegacyWorkflow()));
};

export const setWorkflow = (nextState) => {
    const normalized = mergeDeep(clone(defaultWorkflow), nextState || {});
    inMemoryWorkflowCanonical = legacyToCanonical(normalized);
    shadowMeta.updatedAt = Date.now();
    persistWorkflowShadow();
    dispatchWorkflowUpdated(getWorkflow());
    scheduleWorkflowPersist();
    return getWorkflow();
};

export const updateWorkflow = (patch) => {
    const current = getWorkflow();
    const beforeMerge = JSON.stringify(current);
    const merged = mergeDeep(current, patch || {});
    if (JSON.stringify(merged) === beforeMerge) {
        return current;
    }
    return setWorkflow(merged);
};

export const resetWorkflow = () => {
    inMemoryWorkflowCanonical = createDefaultCanonicalWorkflow();
    shadowMeta.updatedAt = Date.now();
    persistWorkflowShadow();
    dispatchWorkflowUpdated(getWorkflow());
    scheduleWorkflowPersist();
    return getWorkflow();
};

const hasMeaningfulWorkflowData = (workflow) => {
    const current = workflow || {};
    return Boolean(
        (current.billText && String(current.billText).trim()) ||
        current.extraction?.fileName ||
        current.metadata?.title ||
        (Array.isArray(current.similarBills) && current.similarBills.length > 0) ||
        current.billAnalysis?.report ||
        current.legalAnalysis?.report ||
        current.stakeholderAnalysis?.report ||
        current.finalReport?.generatedAt
    );
};

const buildHistoryEntry = (workflow, reason = 'manual') => {
    const now = new Date().toISOString();
    const title = workflow?.metadata?.title || workflow?.extraction?.fileName || 'Untitled Workflow';
    const id = `wf_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
    return {
        id,
        savedAt: now,
        reason,
        title,
        currentStep: workflow?.currentStep || '/',
        summary: {
            fileName: workflow?.extraction?.fileName || '',
            hasMetadata: Boolean(workflow?.metadata?.title || workflow?.metadata?.description || workflow?.metadata?.summary),
            similarBillsCount: Array.isArray(workflow?.similarBills) ? workflow.similarBills.length : 0,
            hasFinalReport: Boolean(workflow?.finalReport?.generatedAt)
        },
        snapshot: mergeDeep(clone(defaultWorkflow), clone(workflow || {}))
    };
};

export const getWorkflowHistory = () => getHistory();

export const archiveWorkflow = (workflow = getWorkflow(), reason = 'manual') => {
    if (!hasMeaningfulWorkflowData(workflow)) return null;
    const entry = buildHistoryEntry(workflow, reason);
    const history = getHistory();
    const nextHistory = [entry, ...history].slice(0, HISTORY_LIMIT);
    setHistory(nextHistory);
    sendAuthenticatedRequest('/api/workflow/history/archive', {
        method: 'POST',
        body: {
            title: entry.title,
            reason: entry.reason,
            current_step: entry.currentStep,
            summary: entry.summary,
            snapshot: entry.snapshot,
        },
    }).catch((error) => logger.warn('Failed to archive workflow remotely', { error }));
    return entry;
};

export const restoreWorkflowFromHistory = (historyId) => {
    const history = getHistory();
    const item = history.find((entry) => entry?.id === historyId);
    if (!item?.snapshot) return null;
    const next = setWorkflow(item.snapshot);
    sendAuthenticatedRequest('/api/workflow/history/restore', {
        method: 'POST',
        body: { history_id: historyId },
    }).catch((error) => logger.warn('Failed to restore workflow remotely', { error }));
    return next;
};

export const deleteWorkflowFromHistory = (historyId) => {
    const history = getHistory();
    const nextHistory = history.filter((entry) => entry?.id !== historyId);
    setHistory(nextHistory);
    sendAuthenticatedRequest(`/api/workflow/history/${historyId}`, {
        method: 'DELETE',
    }).catch((error) => logger.warn('Failed to delete workflow history remotely', { error }));
    return nextHistory;
};

export const resetStepByPath = (path) => {
    const defaults = clone(defaultWorkflow);
    const current = getWorkflow();
    const normalizedPath = normalizeStepPath(path);
    const patch = { currentStep: normalizedPath };
    const fallbackBaseText = (
        current.fixApplicationBaseText ||
        current.extraction?.originalText ||
        current.extraction?.editedText ||
        current.billText ||
        ''
    );
    const recomputeWorkflow = {
        ...current,
        fixApplicationBaseText: fallbackBaseText
    };

    const resetSections = (sectionKeys) => {
        sectionKeys.forEach((key) => {
            patch[key] = defaults[key];
        });
    };

    const resetTracking = (trackingKeys, fullReset = false) => {
        if (fullReset) {
            patch.requestTracking = defaults.requestTracking;
            return;
        }
        const nextTracking = { ...current.requestTracking };
        trackingKeys.forEach((key) => {
            nextTracking[key] = defaults.requestTracking[key];
        });
        patch.requestTracking = nextTracking;
    };

    const syncBillState = (nextBillText) => {
        patch.billText = nextBillText;
        patch.fixApplicationBaseText = fallbackBaseText;
        patch.extraction = {
            ...current.extraction,
            editedText: nextBillText
        };
        patch.billFixes = {
            ...(patch.billFixes || current.billFixes),
            billText: nextBillText
        };
        patch.legalFixes = {
            ...(patch.legalFixes || current.legalFixes),
            billText: nextBillText
        };
        patch.stakeholderFixes = {
            ...(patch.stakeholderFixes || current.stakeholderFixes),
            billText: nextBillText
        };
    };

    const recomputeAfterClearingSource = (sourceKey) => {
        const nextSets = getAppliedSetsFromWorkflow(recomputeWorkflow);
        nextSets[sourceKey] = new Set();

        const pools = getFixPoolsFromWorkflow(recomputeWorkflow);
        const result = recomputeBillTextFromAppliedSets(recomputeWorkflow, nextSets, pools);
        const nextBillText = result.errors.length > 0
            ? fallbackBaseText
            : result.billText;

        syncBillState(nextBillText);
    };

    const resetFromExtraction = () => {
        resetSections([
            'billText',
            'fixApplicationBaseText',
            'extraction',
            'metadata',
            'similarBills',
            'similarBillsStats',
            'similarBillsLoaded',
            'billAnalysis',
            'billFixes',
            'legalAnalysis',
            'legalFixes',
            'stakeholderAnalysis',
            'stakeholderFixes',
            'finalReport'
        ]);
        resetTracking([], true);
    };

    const resetFromMetadata = () => {
        resetSections([
            'metadata',
            'similarBills',
            'similarBillsStats',
            'similarBillsLoaded',
            'billAnalysis',
            'billFixes',
            'legalAnalysis',
            'legalFixes',
            'stakeholderAnalysis',
            'stakeholderFixes',
            'finalReport'
        ]);
        resetTracking(['metadata', 'similarity', 'loader', 'billAnalysis', 'conflictAnalysis', 'stakeholderAnalysis']);
    };

    const resetFromSimilarity = () => {
        resetSections([
            'similarBills',
            'similarBillsStats',
            'similarBillsLoaded',
            'billAnalysis',
            'billFixes',
            'legalAnalysis',
            'legalFixes',
            'stakeholderAnalysis',
            'stakeholderFixes',
            'finalReport'
        ]);
        resetTracking(['similarity', 'loader', 'billAnalysis', 'conflictAnalysis', 'stakeholderAnalysis']);
    };

    const resetFromLoader = () => {
        resetSections([
            'similarBillsLoaded',
            'billAnalysis',
            'billFixes',
            'legalAnalysis',
            'legalFixes',
            'stakeholderAnalysis',
            'stakeholderFixes',
            'finalReport'
        ]);
        resetTracking(['loader', 'billAnalysis', 'conflictAnalysis', 'stakeholderAnalysis']);
    };

    const resetFromBillAnalysis = () => {
        resetSections([
            'billAnalysis',
            'billFixes',
            'legalAnalysis',
            'legalFixes',
            'stakeholderAnalysis',
            'stakeholderFixes',
            'finalReport'
        ]);
        resetTracking(['billAnalysis', 'conflictAnalysis', 'stakeholderAnalysis']);
    };

    const resetFromLegalAnalysis = () => {
        resetSections([
            'legalAnalysis',
            'legalFixes',
            'stakeholderAnalysis',
            'stakeholderFixes',
            'finalReport'
        ]);
        resetTracking(['conflictAnalysis', 'stakeholderAnalysis']);
    };

    const resetFromStakeholderAnalysis = () => {
        resetSections(['stakeholderAnalysis', 'stakeholderFixes', 'finalReport']);
        resetTracking(['stakeholderAnalysis']);
    };

    switch (normalizedPath) {
        case STEP_PATHS.EXTRACTION_INPUT:
        case STEP_PATHS.EXTRACTION_OUTPUT:
            resetFromExtraction();
            break;
        case STEP_PATHS.DOCUMENT:
        case STEP_PATHS.METADATA:
            resetFromMetadata();
            break;
        case STEP_PATHS.SIMILAR_BILLS:
            resetFromSimilarity();
            break;
        case STEP_PATHS.SIMILAR_BILLS_LOADER:
            resetFromLoader();
            break;
        case STEP_PATHS.BILL_ANALYSIS_REPORT:
            resetFromBillAnalysis();
            break;
        case STEP_PATHS.BILL_ANALYSIS_FIXES:
            patch.billFixes = defaults.billFixes;
            recomputeAfterClearingSource('bill');
            break;
        case STEP_PATHS.LEGAL_ANALYSIS_REPORT:
            resetFromLegalAnalysis();
            break;
        case STEP_PATHS.LEGAL_ANALYSIS_FIXES:
            patch.legalFixes = defaults.legalFixes;
            recomputeAfterClearingSource('legal');
            break;
        case STEP_PATHS.STAKEHOLDER_REPORT:
            resetFromStakeholderAnalysis();
            break;
        case STEP_PATHS.STAKEHOLDER_FIXES:
            patch.stakeholderFixes = defaults.stakeholderFixes;
            recomputeAfterClearingSource('stakeholder');
            break;
        case STEP_PATHS.FINAL_REPORT:
        case STEP_PATHS.FINAL_EDITING:
            patch.finalReport = defaults.finalReport;
            break;
        default:
            break;
    }

    return updateWorkflow(patch);
};

export { STEP_PATHS };
