import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';
import { updateWorkflow } from '../utils/workflowStorage';
import { setRequestTracking } from '../utils/requestTracking';
import PageShell from '../components/layout/PageShell';
import { API_CONFIG } from '../config/api';
import { useTaskPolling } from '../hooks/useTaskPolling';
import { STEP_PATHS } from '../workflow/definitions';
import { useWorkflowState } from '../hooks/useWorkflowState';

const STATE = {
    LOADING: 'loading',
    COMPLETE: 'complete',
    ERROR: 'error'
};

const CATEGORIES = [
    'Citations',
    'Exemptions',
    'Definitions',
    'Requirements',
    'Prohibitions',
    'Enforcement Mechanisms',
    'Findings and Declarations',
    'Other'
];

function SimilarBillsLoaderPage() {
    const navigate = useNavigate();
    const { workflow } = useWorkflowState();
    const hasStartedRef = useRef(false);
    const lastPartialLengthRef = useRef(0);

    const [currentState, setCurrentState] = useState(STATE.LOADING);
    const [loadedBillsData, setLoadedBillsData] = useState(null);
    const [streamedBills, setStreamedBills] = useState([]);
    const [userBillCategorized, setUserBillCategorized] = useState(null);
    const [llmCallCount, setLlmCallCount] = useState(0);
    const [lastCallBillCount, setLastCallBillCount] = useState(0);
    const [error, setError] = useState(null);
    const loaderStatus = workflow.requestTracking?.loader?.status;

    const loaderPolling = useTaskPolling({
        intervalMs: API_CONFIG.POLL_INTERVAL,
        start: async () => {
            const requestId = apiService.generateRequestId();
            setRequestTracking('loader', requestId, 'running');

            const startResponse = await apiService.loadSimilarBills(
                workflow.similarBills,
                workflow.billText,
                workflow.metadata,
                'CA',
                requestId
            );

            const effectiveRequestId = startResponse.request_id || requestId;
            if (effectiveRequestId !== requestId) {
                setRequestTracking('loader', effectiveRequestId, 'running');
            }
            if (!startResponse.success && startResponse.status !== 'running') {
                throw new Error(startResponse.data?.Error || 'Failed to start similar bills loader');
            }

            return { ...startResponse, request_id: effectiveRequestId };
        },
        status: async (requestId) => {
            return apiService.getSimilarBillsLoaderStatus(requestId);
        },
        result: async (requestId) => {
            return apiService.getSimilarBillsLoaderResult(requestId);
        },
        onPartial: (partial) => {
            if (!partial) return;

            let partialUserBill = null;
            let partialBills = null;

            if (Array.isArray(partial)) {
                partialBills = partial;
            } else if (typeof partial === 'object') {
                partialUserBill = partial.user_bill || null;
                if (Array.isArray(partial.similar_bills)) {
                    partialBills = partial.similar_bills;
                }
            }

            if (partialUserBill) {
                setUserBillCategorized(partialUserBill);
            }

            if (Array.isArray(partialBills)) {
                const previousLength = lastPartialLengthRef.current;
                const delta = partialBills.length - previousLength;
                if (delta !== 0) {
                    setLlmCallCount((prev) => prev + 1);
                    setLastCallBillCount(Math.abs(delta));
                }
                setStreamedBills(partialBills);
                lastPartialLengthRef.current = partialBills.length;
            }
        }
    });

    useEffect(() => {
        if (!workflow.similarBills || workflow.similarBills.length === 0) {
            navigate(STEP_PATHS.SIMILAR_BILLS);
            return;
        }

        if (workflow.currentStep !== STEP_PATHS.SIMILAR_BILLS_LOADER) {
            updateWorkflow({ currentStep: STEP_PATHS.SIMILAR_BILLS_LOADER });
        }

        if (workflow.similarBillsLoaded?.data) {
            setLoadedBillsData(workflow.similarBillsLoaded.data);
            setCurrentState(STATE.COMPLETE);
            return;
        }

        if (!hasStartedRef.current) {
            hasStartedRef.current = true;
            const tracking = workflow.requestTracking?.loader;
            if ((tracking?.status === 'running' || tracking?.status === 'completed') && tracking?.requestId) {
                loadSimilarBillsData(tracking.requestId);
            } else {
                loadSimilarBillsData();
            }
        }
    }, [
        navigate,
        workflow.currentStep,
        workflow.requestTracking?.loader,
        workflow.similarBills,
        workflow.similarBillsLoaded?.data
    ]);

    const loadSimilarBillsData = async (existingRequestId = null) => {
        setCurrentState(STATE.LOADING);
        setError(null);
        setStreamedBills([]);
        setUserBillCategorized(null);
        setLlmCallCount(0);
        setLastCallBillCount(0);
        lastPartialLengthRef.current = 0;

        const outcome = await loaderPolling.run({
            existingRequestId,
            startIfMissing: !existingRequestId,
            initialOperation: 'Loading similar bills...'
        });

        if (outcome?.cancelled) {
            return;
        }

        const hasPassedBills = Array.isArray(outcome?.data?.Passed_Bills);
        const hasFailedBills = Array.isArray(outcome?.data?.Failed_Bills);
        if (outcome?.ok && hasPassedBills && hasFailedBills) {
            setLoadedBillsData(outcome.data);
            updateWorkflow({
                similarBillsLoaded: { data: outcome.data, expandedBillIds: [] }
            });
            setRequestTracking('loader', outcome.requestId, 'completed');
            setCurrentState(STATE.COMPLETE);
            return;
        }

        const errorMessage = (
            outcome?.error ||
            outcome?.terminalStatus?.error ||
            outcome?.terminalStatus?.data?.Error ||
            'Failed to load similar bills'
        );
        setError(errorMessage);
        setRequestTracking('loader', outcome?.requestId || existingRequestId || null, 'failed');
        setCurrentState(STATE.ERROR);
    };

    const handleContinue = () => {
        updateWorkflow({ currentStep: STEP_PATHS.BILL_ANALYSIS_REPORT });
        navigate(STEP_PATHS.BILL_ANALYSIS_REPORT);
    };

    const handleInspectBill = (bill, source = 'loaded') => {
        const billId = bill?.Bill_ID || bill?.['Bill ID'] || '';
        const params = new URLSearchParams({ source });
        if (billId) params.set('billId', String(billId));
        const displayTitle = bill?.Bill_Title || bill?.Title || bill?.Bill_Number || `Bill ${billId}`;
        navigate(`/bill-inspect?${params.toString()}`, {
            state: {
                title: displayTitle,
                description: bill?.Bill_Description || '',
                billText: bill?.Bill_Text || ''
            }
        });
    };

    const handleInspectUserBill = () => {
        const params = new URLSearchParams({ source: 'user' });
        navigate(`/bill-inspect?${params.toString()}`, {
            state: {
                title: workflow.metadata?.title || 'User Bill',
                description: workflow.metadata?.description || '',
                billText: workflow.billText || workflow.extraction?.editedText || ''
            }
        });
    };

    const getCategoryColor = (category) => {
        const colors = {
            Citations: '#E3F2FD',
            Exemptions: '#FFF3E0',
            Definitions: '#F3E5F5',
            Requirements: '#E8F5E9',
            Prohibitions: '#FFEBEE',
            'Enforcement Mechanisms': '#FFF9C4',
            'Findings and Declarations': '#E0F2F1',
            Other: '#F5F5F5'
        };
        return colors[category] || '#F5F5F5';
    };

    const getCategoriesPayload = (bill) => bill?.Categorized_Sentences || bill || {};
    const getCategoryCount = (payload, category) => {
        const value = payload?.[category];
        return Array.isArray(value) ? value.length : 0;
    };

    const renderCollapsedBill = (bill, keyPrefix, source = 'loaded') => {
        const billId = String(bill?.Bill_ID || bill?.['Bill ID'] || 'unknown');
        const billNumber = bill?.Bill_Number || bill?.['Bill Number'] || null;
        const title = bill?.Bill_Title || bill?.Title || billNumber || `Bill ${billId}`;
        const description = bill?.Bill_Description || bill?.Description || 'No description available.';
        const billUrl = bill?.Bill_URL || bill?.['Bill URL'] || null;
        const categories = getCategoriesPayload(bill);
        const isPassed = typeof bill?.Passed === 'boolean' ? bill.Passed : null;

        return (
            <details
                key={`${keyPrefix}-${billId}`}
                style={{
                    border: '1px solid #EAE3D5',
                    borderRadius: '4px',
                    background: '#fff',
                    padding: '12px 14px'
                }}
            >
                <summary style={{ cursor: 'pointer', listStyle: 'none' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                            <span style={{ fontSize: '14px', fontWeight: 600, color: '#1C1C1C' }}>{title}</span>
                            {billNumber && (
                                <span style={{ fontSize: '11px', color: '#6B5444' }}>{billNumber}</span>
                            )}
                            {isPassed != null && (
                                <span style={{
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                    fontSize: '10px',
                                    fontWeight: 700,
                                    textTransform: 'uppercase',
                                    backgroundColor: isPassed ? '#E8F5E9' : '#FFEBEE',
                                    color: isPassed ? '#2E7D32' : '#C62828',
                                    border: `1px solid ${isPassed ? '#C8E6C9' : '#FFCDD2'}`
                                }}>
                                    {isPassed ? 'Passed' : 'Failed'}
                                </span>
                            )}
                            <span style={{ fontSize: '11px', color: '#8B7355' }}>Internal ID: {billId}</span>
                        </div>
                        <span style={{ fontSize: '11px', color: '#8B7355' }}>Click to expand</span>
                    </div>
                </summary>

                <div style={{ marginTop: '10px', borderTop: '1px solid #EAE3D5', paddingTop: '10px' }}>
                    <p style={{ fontSize: '13px', color: '#6B5444', lineHeight: '1.55', margin: '0 0 10px 0' }}>
                        {description}
                    </p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '10px' }}>
                        {CATEGORIES.map((category) => {
                            const count = getCategoryCount(categories, category);
                            if (count === 0) return null;
                            return (
                                <span key={`${billId}-${category}`} style={{
                                    padding: '3px 8px',
                                    borderRadius: '4px',
                                    fontSize: '10px',
                                    fontWeight: 600,
                                    backgroundColor: getCategoryColor(category),
                                    color: '#374151',
                                    border: '1px solid rgba(0,0,0,0.1)'
                                }}>
                                    {category}: {count}
                                </span>
                            );
                        })}
                    </div>

                    <details>
                        <summary style={{ cursor: 'pointer', fontSize: '11px', fontWeight: 700, color: '#6B5444' }}>
                            View categorized sentence preview
                        </summary>
                        <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {CATEGORIES.map((category) => {
                                const items = categories?.[category];
                                if (!Array.isArray(items) || items.length === 0) return null;
                                return (
                                    <details key={`${billId}-${category}-items`}>
                                        <summary style={{ cursor: 'pointer', fontSize: '11px', color: '#6B5444' }}>
                                            {category} ({items.length})
                                        </summary>
                                        <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                            {items.slice(0, 3).map((item, idx) => (
                                                <div key={`${billId}-${category}-item-${idx}`} style={{
                                                    fontSize: '12px',
                                                    color: '#6B5444',
                                                    background: '#FDFCF8',
                                                    borderLeft: `3px solid ${getCategoryColor(category)}`,
                                                    borderRadius: '2px',
                                                    padding: '8px'
                                                }}>
                                                    {item}
                                                </div>
                                            ))}
                                        </div>
                                    </details>
                                );
                            })}
                        </div>
                    </details>

                    <div style={{ marginTop: '10px', display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
                        {billUrl && (
                            <a
                                href={billUrl}
                                target="_blank"
                                rel="noreferrer"
                                style={{ fontSize: '12px', color: '#2563EB' }}
                            >
                                Open official bill page
                            </a>
                        )}
                        <button className="clause-btn clause-btn-secondary" onClick={() => handleInspectBill(bill, source)}>
                            Inspect Bill
                        </button>
                    </div>
                </div>
            </details>
        );
    };

    const allLoadedBills = [
        ...(loadedBillsData?.Passed_Bills || []),
        ...(loadedBillsData?.Failed_Bills || [])
    ];
    const loadingPassedCount = streamedBills.filter((bill) => bill.Passed === true).length;
    const loadingFailedCount = streamedBills.filter((bill) => bill.Passed === false).length;
    const hasProgress = typeof loaderPolling.progress === 'number';

    return (
        <PageShell title="Similar Bills Loader" subtitle="Categorize candidate bills with collapsed detail views and inspect on demand.">
            <div style={{ padding: '8px 0' }}>
                <div style={{ maxWidth: '1100px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {loaderStatus && (
                        <div style={{ fontSize: '12px', color: '#8B7355' }}>
                            Status: {loaderStatus}
                        </div>
                    )}

                    {error && (
                        <div style={{
                            backgroundColor: '#FEF2F2',
                            border: '1px solid #F5C3BE',
                            borderRadius: '4px',
                            padding: '12px 14px',
                            fontSize: '12px',
                            color: '#B42318'
                        }}>
                            {error}
                        </div>
                    )}

                    <div style={{
                        background: '#FDFCF8',
                        border: '1px solid #EAE3D5',
                        borderRadius: '4px',
                        padding: '24px'
                    }}>
                        {currentState === STATE.LOADING && (
                            <>
                                <div style={{
                                    width: '100%',
                                    height: '4px',
                                    backgroundColor: '#EAE3D5',
                                    borderRadius: '2px',
                                    overflow: 'hidden',
                                    marginBottom: '12px'
                                }}>
                                    <div style={{
                                        width: `${hasProgress ? loaderPolling.progress : 100}%`,
                                        height: '100%',
                                        background: 'linear-gradient(90deg, #C5A47E 0%, #D4B896 100%)',
                                        opacity: hasProgress ? 1 : 0.55,
                                        transition: 'width 0.5s ease'
                                    }} />
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                                    <span style={{ fontSize: '13px', color: '#6B5444' }}>{loaderPolling.operation}</span>
                                    <span style={{ fontSize: '12px', color: '#8B7355' }}>
                                        LLM calls: {llmCallCount} • last batch: {lastCallBillCount} • passed: {loadingPassedCount} • failed: {loadingFailedCount}
                                        {hasProgress ? ` • ${loaderPolling.progress}%` : ' • syncing status...'}
                                    </span>
                                </div>
                            </>
                        )}

                        {currentState === STATE.COMPLETE && (
                            <div style={{ fontSize: '14px', color: '#6B5444' }}>
                                Loading complete. {loadedBillsData?.Passed_Bills?.length || 0} passed and {loadedBillsData?.Failed_Bills?.length || 0} failed bills are ready.
                            </div>
                        )}
                    </div>

                    {userBillCategorized && (
                        <details style={{ border: '1px solid #EAE3D5', borderRadius: '4px', background: '#fff', padding: '12px 14px' }}>
                            <summary style={{ cursor: 'pointer', listStyle: 'none' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px' }}>
                                    <span style={{ fontSize: '14px', fontWeight: 600, color: '#1C1C1C' }}>User Bill (categorized)</span>
                                    <span style={{ fontSize: '11px', color: '#8B7355' }}>Click to expand</span>
                                </div>
                            </summary>
                            <div style={{ marginTop: '10px', borderTop: '1px solid #EAE3D5', paddingTop: '10px' }}>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '10px' }}>
                                    {CATEGORIES.map((category) => {
                                        const count = getCategoryCount(userBillCategorized, category);
                                        if (count === 0) return null;
                                        return (
                                            <span key={`user-${category}`} style={{
                                                padding: '3px 8px',
                                                borderRadius: '4px',
                                                fontSize: '10px',
                                                fontWeight: 600,
                                                backgroundColor: getCategoryColor(category),
                                                color: '#374151',
                                                border: '1px solid rgba(0,0,0,0.1)'
                                            }}>
                                                {category}: {count}
                                            </span>
                                        );
                                    })}
                                </div>
                                <button className="clause-btn clause-btn-secondary" onClick={handleInspectUserBill}>
                                    Inspect User Bill
                                </button>
                            </div>
                        </details>
                    )}

                    {currentState === STATE.LOADING && streamedBills.length > 0 && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            {streamedBills.map((bill, idx) => renderCollapsedBill(bill, `stream-${idx}`, 'stream'))}
                        </div>
                    )}

                    {currentState === STATE.COMPLETE && loadedBillsData && (
                        <>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                                {allLoadedBills.map((bill, idx) => renderCollapsedBill(bill, `loaded-${idx}`, 'loaded'))}
                            </div>

                            <button className="clause-btn clause-btn-primary" style={{ width: '100%', padding: '14px 24px' }} onClick={handleContinue}>
                                Generate Bill Analysis
                            </button>
                        </>
                    )}
                </div>
            </div>
        </PageShell>
    );
}

export default SimilarBillsLoaderPage;
