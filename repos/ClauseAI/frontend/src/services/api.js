import { API_CONFIG } from '../config/api';
import { createLogger } from '../utils/logger';
import { getAccessToken } from '../lib/supabaseClient';

const logger = createLogger('APIService');

const TASK_ENDPOINTS = {
    loader: {
        start: '/api/similar_bills_loader/load-similar-bills',
        status: '/api/similar_bills_loader/load-similar-bills/status',
        result: '/api/similar_bills_loader/load-similar-bills/result'
    },
    billAnalysis: {
        start: '/api/bill_analysis/analyze-bill',
        status: '/api/bill_analysis/analyze-bill/status',
        result: '/api/bill_analysis/analyze-bill/result'
    },
    conflictAnalysis: {
        start: '/api/conflict_analysis/analyze-conflicts',
        status: '/api/conflict_analysis/analyze-conflicts/status',
        result: '/api/conflict_analysis/analyze-conflicts/result'
    },
    stakeholderAnalysis: {
        start: '/api/stakeholder_analysis/analyze-stakeholders',
        status: '/api/stakeholder_analysis/analyze-stakeholders/status',
        result: '/api/stakeholder_analysis/analyze-stakeholders/result'
    }
};

class APIError extends Error {
    constructor(message, statusCode, data) {
        super(message);
        this.name = 'APIError';
        this.statusCode = statusCode;
        this.data = data;
    }
}

class APIService {
    constructor() {
        this.baseURL = API_CONFIG.BASE_URL;
        this.timeout = API_CONFIG.TIMEOUT;
        this.statusInflight = new Map();
        this.statusRecent = new Map();
        this.statusBackoff = new Map();
        logger.info('API service initialized', {
            baseURL: this.baseURL,
            timeoutMs: this.timeout,
        });
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);
        const skipAuth = options.skipAuth === true;
        const method = options.method || 'GET';
        const startedAt = performance.now();

        try {
            const accessToken = skipAuth ? null : await getAccessToken();
            if (!skipAuth && !accessToken) {
                throw new APIError('Unauthorized', 401);
            }
            const response = await fetch(url, {
                ...options,
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {})
                },
            });

            clearTimeout(timeoutId);
            const durationMs = Math.round(performance.now() - startedAt);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                logger.warn('Request failed with non-OK status', {
                    endpoint,
                    method,
                    status: response.status,
                    durationMs,
                    errorData,
                });
                throw new APIError(
                    errorData.message || 'Request failed',
                    response.status,
                    errorData
                );
            }

            const responseJson = await response.json();
            logger.debug('Request completed', {
                endpoint,
                method,
                status: response.status,
                durationMs,
            });
            return responseJson;
        } catch (error) {
            clearTimeout(timeoutId);
            const durationMs = Math.round(performance.now() - startedAt);

            if (error.name === 'AbortError') {
                logger.error('Request timed out', { endpoint, method, durationMs });
                throw new APIError('Request timeout', 408);
            }

            if (error instanceof APIError) {
                throw error;
            }

            logger.error('Network or unexpected request failure', {
                endpoint,
                method,
                durationMs,
                error,
            });
            throw new APIError(
                error.message || 'Network error',
                0,
                { originalError: error }
            );
        }
    }

    withRequestId(requestId) {
        return requestId || this.generateRequestId();
    }

    async sleep(ms) {
        if (!ms || ms <= 0) return;
        await new Promise((resolve) => setTimeout(resolve, ms));
    }

    async postWithRequestId(endpoint, body, requestId) {
        const request_id = this.withRequestId(requestId);
        const response = await this.post(endpoint, { ...body, request_id });
        return {
            ...response,
            request_id: response?.request_id || request_id
        };
    }

    resolveAnalysisOptions(options = {}) {
        return {
            phase: options?.phase || 'report',
            reportContext: options?.reportContext || null,
        };
    }

    async startTask(descriptor, payload, requestId) {
        if (!descriptor?.start) {
            throw new APIError('Invalid task descriptor (missing start endpoint)', 500);
        }
        return this.postWithRequestId(descriptor.start, payload || {}, requestId);
    }

    async fetchTaskStatus(descriptor, requestId) {
        if (!descriptor?.status) {
            throw new APIError('Invalid task descriptor (missing status endpoint)', 500);
        }
        const url = `${descriptor.status}?request_id=${requestId}`;
        const key = `${descriptor.status}:${requestId}`;
        const now = Date.now();

        const inFlight = this.statusInflight.get(key);
        if (inFlight) {
            return inFlight;
        }

        const recent = this.statusRecent.get(key);
        if (recent && (now - recent.timestamp) < API_CONFIG.STATUS_MIN_INTERVAL) {
            return recent.promise;
        }

        const promise = (async () => {
            const backoff = this.statusBackoff.get(key);
            if (backoff?.nextAllowedAt && backoff.nextAllowedAt > Date.now()) {
                await this.sleep(backoff.nextAllowedAt - Date.now());
            }

            try {
                const status = await this.get(url);
                this.statusBackoff.delete(key);
                return status;
            } catch (error) {
                if (error?.statusCode === 429) {
                    const previousDelay = this.statusBackoff.get(key)?.delayMs || 0;
                    const nextDelay = previousDelay > 0
                        ? Math.min(15000, previousDelay * 2)
                        : 1000;
                    this.statusBackoff.set(key, {
                        delayMs: nextDelay,
                        nextAllowedAt: Date.now() + nextDelay
                    });
                }
                throw error;
            } finally {
                this.statusInflight.delete(key);
            }
        })();

        this.statusInflight.set(key, promise);
        this.statusRecent.set(key, {
            timestamp: now,
            promise
        });
        return promise;
    }

    async fetchTaskResult(descriptor, requestId) {
        if (!descriptor?.result) {
            throw new APIError('Invalid task descriptor (missing result endpoint)', 500);
        }
        return this.get(`${descriptor.result}?request_id=${requestId}`);
    }

    async get(endpoint, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'GET',
        });
    }

    async post(endpoint, data, options = {}) {
        return this.request(endpoint, {
            ...options,
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    generateRequestId() {
        if (window.crypto && window.crypto.randomUUID) {
            return window.crypto.randomUUID();
        }
        return `req_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    }

    async checkHealth() {
        try {
            const response = await this.get('/health', { skipAuth: true });
            return {
                isHealthy: response.status === 'healthy',
                version: response.version,
            };
        } catch (error) {
            logger.warn('Health check failed', { error });
            return {
                isHealthy: false,
                version: null,
                error: error.message,
            };
        }
    }

    async getAuthStatus() {
        const [status, token] = await Promise.all([
            this.get('/auth/status', { skipAuth: true }).catch(() => ({ enabled: false })),
            getAccessToken().catch(() => null),
        ]);
        return {
            ...status,
            authenticated: Boolean(token),
        };
    }

    async getCurrentUserProfile() {
        return this.get('/api/user/me');
    }

    async updateCurrentUserProfile(patch) {
        return this.request('/api/user/me', {
            method: 'PATCH',
            body: JSON.stringify(patch || {}),
        });
    }

    async getCurrentWorkflow() {
        return this.get('/api/workflow/current');
    }

    async saveCurrentWorkflow(workflow, currentStep = null) {
        return this.request('/api/workflow/current', {
            method: 'PUT',
            body: JSON.stringify({
                workflow: workflow || {},
                current_step: currentStep,
            }),
        });
    }

    async getWorkflowHistory() {
        return this.get('/api/workflow/history');
    }

    async archiveWorkflowHistory(payload) {
        return this.post('/api/workflow/history/archive', payload || {});
    }

    async restoreWorkflowHistory(historyId) {
        return this.post('/api/workflow/history/restore', { history_id: historyId });
    }

    async deleteWorkflowHistory(historyId) {
        return this.request(`/api/workflow/history/${historyId}`, { method: 'DELETE' });
    }

    async extractBillText(fileContentOrPayload, fileType, requestId) {
        const body = (
            fileContentOrPayload &&
            typeof fileContentOrPayload === 'object' &&
            !Array.isArray(fileContentOrPayload)
        )
            ? fileContentOrPayload
            : {
                file_content: fileContentOrPayload,
                file_type: fileType,
            };
        return this.postWithRequestId('/api/bill_extraction/extract-text', body, requestId);
    }

    async generateMetadata(billText, requestId) {
        return this.postWithRequestId('/api/title_description/generate-metadata', {
            bill_text: billText,
            example_bill: null,
            example_title: null,
            example_description: null,
            example_summary: null
        }, requestId);
    }

    async findSimilarBills(title, description, summary, jurisdiction = 'CA', requestId) {
        return this.postWithRequestId('/api/bill_similarity/find-similar', {
            title,
            description,
            summary,
            jurisdiction
        }, requestId);
    }

    async loadSimilarBills(similarityMatches, userBillText, userBillMetadata, jurisdiction = 'CA', requestId) {
        return this.startTask(TASK_ENDPOINTS.loader, {
            similarity_matches: similarityMatches,
            user_bill_text: userBillText,
            user_bill_metadata: userBillMetadata,
            jurisdiction
        }, requestId);
    }

    async getSimilarBillsLoaderStatus(requestId) {
        return this.fetchTaskStatus(TASK_ENDPOINTS.loader, requestId);
    }

    async getSimilarBillsLoaderResult(requestId) {
        return this.fetchTaskResult(TASK_ENDPOINTS.loader, requestId);
    }

    async analyzeBill(
        userBill,
        userBillRawText,
        passedBills,
        failedBills,
        policyArea,
        jurisdiction = 'CA',
        requestId,
        options = {}
    ) {
        const { phase, reportContext } = this.resolveAnalysisOptions(options);
        return this.startTask(TASK_ENDPOINTS.billAnalysis, {
            user_bill: userBill,
            user_bill_raw_text: userBillRawText,
            passed_bills: passedBills,
            failed_bills: failedBills,
            policy_area: policyArea,
            jurisdiction,
            phase,
            report_context: reportContext
        }, requestId);
    }

    async getBillAnalysisStatus(requestId) {
        return this.fetchTaskStatus(TASK_ENDPOINTS.billAnalysis, requestId);
    }

    async getBillAnalysisResult(requestId) {
        return this.fetchTaskResult(TASK_ENDPOINTS.billAnalysis, requestId);
    }

    async analyzeConflicts(billText, requestId, options = {}) {
        const { phase, reportContext } = this.resolveAnalysisOptions(options);
        return this.startTask(TASK_ENDPOINTS.conflictAnalysis, {
            bill_text: billText,
            phase,
            report_context: reportContext
        }, requestId);
    }

    async getConflictAnalysisStatus(requestId) {
        return this.fetchTaskStatus(TASK_ENDPOINTS.conflictAnalysis, requestId);
    }

    async getConflictAnalysisResult(requestId) {
        return this.fetchTaskResult(TASK_ENDPOINTS.conflictAnalysis, requestId);
    }

    async analyzeStakeholders(billText, requestId, options = {}) {
        const { phase, reportContext } = this.resolveAnalysisOptions(options);
        return this.startTask(TASK_ENDPOINTS.stakeholderAnalysis, {
            bill_text: billText,
            phase,
            report_context: reportContext
        }, requestId);
    }

    async getStakeholderAnalysisStatus(requestId) {
        return this.fetchTaskStatus(TASK_ENDPOINTS.stakeholderAnalysis, requestId);
    }

    async getStakeholderAnalysisResult(requestId) {
        return this.fetchTaskResult(TASK_ENDPOINTS.stakeholderAnalysis, requestId);
    }

    async inspectBill(payload = {}, requestId) {
        return this.postWithRequestId('/api/bill_inspect/inspect', payload, requestId);
    }
}

export const apiService = new APIService();
