import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';
import { updateWorkflow } from '../utils/workflowStorage';
import { setRequestTracking } from '../utils/requestTracking';
import PageShell from '../components/layout/PageShell';
import { STEP_PATHS } from '../workflow/definitions';
import { useWorkflowState } from '../hooks/useWorkflowState';

const STATE = {
    LOADING: 'loading',
    COMPLETE: 'complete',
    ERROR: 'error'
};

function SimilarBillsPage() {
    const navigate = useNavigate();
    const { workflow } = useWorkflowState();
    const hasStartedRef = useRef(false);
    const [currentState, setCurrentState] = useState(STATE.LOADING);
    const [similarBills, setSimilarBills] = useState([]);
    const [error, setError] = useState(null);
    const [stats, setStats] = useState({ total: 0, passed: 0, failed: 0 });
    const similarityStatus = workflow.requestTracking?.similarity?.status;
    const normalizedMetadata = {
        title: workflow.metadata?.title ?? workflow.metadata?.Title ?? '',
        description: workflow.metadata?.description ?? workflow.metadata?.Description ?? '',
        summary: workflow.metadata?.summary ?? workflow.metadata?.Summary ?? ''
    };
    const metadataReady = Boolean(
        normalizedMetadata.title?.trim() &&
        normalizedMetadata.description?.trim()
    );

    useEffect(() => {
        if (!metadataReady) {
            setCurrentState(STATE.ERROR);
            setError('Metadata is incomplete. Please complete title and description before finding similar bills.');
            return;
        }

        if (workflow.currentStep !== STEP_PATHS.SIMILAR_BILLS) {
            updateWorkflow({ currentStep: STEP_PATHS.SIMILAR_BILLS });
        }

        if (workflow.similarBills && workflow.similarBills.length > 0) {
            setSimilarBills(workflow.similarBills);
            setStats(workflow.similarBillsStats || { total: workflow.similarBills.length, passed: 0, failed: 0 });
            setCurrentState(STATE.COMPLETE);
            return;
        }

        if (!hasStartedRef.current) {
            hasStartedRef.current = true;
            findSimilarBills();
        }
    }, [
        navigate,
        metadataReady,
        workflow.currentStep,
        workflow.metadata?.description,
        workflow.metadata?.summary,
        workflow.metadata?.title,
        workflow.metadata?.Description,
        workflow.metadata?.Summary,
        workflow.metadata?.Title,
        workflow.similarBills,
        workflow.similarBillsStats
    ]);

    const findSimilarBills = async () => {
        setCurrentState(STATE.LOADING);
        setError(null);

        let requestId = null;
        try {
            requestId = apiService.generateRequestId();
            setRequestTracking('similarity', requestId, 'running');
            const response = await apiService.findSimilarBills(
                normalizedMetadata.title,
                normalizedMetadata.description,
                normalizedMetadata.summary || normalizedMetadata.description,
                'CA',
                requestId
            );

            if (response.success && Array.isArray(response.data)) {
                const sortedBills = [...response.data].sort((a, b) => {
                    if (b.Score !== a.Score) {
                        return b.Score - a.Score;
                    }
                    return b.Passed === a.Passed ? 0 : b.Passed ? 1 : -1;
                });

                const passedCount = sortedBills.filter(b => b.Passed).length;
                const failedCount = sortedBills.filter(b => !b.Passed).length;
                const statsResult = {
                    total: sortedBills.length,
                    passed: passedCount,
                    failed: failedCount
                };

                setSimilarBills(sortedBills);
                setStats(statsResult);
                updateWorkflow({
                    similarBills: sortedBills,
                    similarBillsStats: statsResult
                });
                setRequestTracking('similarity', requestId, 'completed');
                setCurrentState(STATE.COMPLETE);
            } else {
                setError(response.data?.Error || 'Failed to find similar bills');
                setRequestTracking('similarity', requestId, 'failed');
                setCurrentState(STATE.ERROR);
            }
        } catch (err) {
            setError(err.message || 'Failed to find similar bills');
            setRequestTracking('similarity', null, 'failed');
            setCurrentState(STATE.ERROR);
        }
    };

    const handleContinue = () => {
        updateWorkflow({ currentStep: STEP_PATHS.SIMILAR_BILLS_LOADER });
        navigate(STEP_PATHS.SIMILAR_BILLS_LOADER);
    };

    const handleInspectBill = (bill) => {
        const params = new URLSearchParams({ source: 'similar' });
        if (bill.Bill_ID) params.set('billId', String(bill.Bill_ID));
        const displayTitle = bill.Bill_Title || bill.Bill_Number || `Bill ${bill.Bill_ID}`;
        const displayDescription = bill.Bill_Description || `Similarity score ${formatScore(bill.Score)} • ${bill.Passed ? 'Passed' : 'Failed'}`;
        navigate(`/bill-inspect?${params.toString()}`, {
            state: {
                title: displayTitle,
                description: displayDescription,
                billText: bill.Bill_Text || ''
            }
        });
    };

    const handleTryAgain = () => {
        if (!metadataReady) return;
        hasStartedRef.current = false;
        findSimilarBills();
    };

    const handleGoToMetadata = () => {
        updateWorkflow({ currentStep: STEP_PATHS.METADATA });
        navigate(STEP_PATHS.METADATA);
    };

    const formatScore = (score) => `${Math.round(score * 100)}%`;

    return (
        <PageShell>
            <div style={{ padding: '8px 0' }}>
                <div style={{ maxWidth: '900px', margin: '0 auto' }}>
                    {currentState === STATE.LOADING && (
                        <div style={{
                            background: '#FDFCF8',
                            border: '1px solid #EAE3D5',
                            borderRadius: '4px',
                            padding: '80px 48px',
                            textAlign: 'center'
                        }}>
                            <div className="clause-spinner" style={{
                                width: '64px',
                                height: '64px',
                                margin: '0 auto 32px',
                                border: '4px solid #EAE3D5',
                                borderTopColor: '#C5A47E',
                                borderRadius: '50%'
                            }} />
                            <h2 style={{
                                fontFamily: "'Crimson Pro', serif",
                                fontSize: '32px',
                                fontWeight: 600,
                                color: '#1C1C1C',
                                marginBottom: '16px'
                            }}>
                                Finding Similar Bills
                            </h2>
                            <p style={{ fontSize: '16px', color: '#6B5444', marginBottom: '8px' }}>
                                Running semantic similarity search
                            </p>
                        </div>
                    )}

                    {error && (
                        <div style={{
                            backgroundColor: '#FEF2F2',
                            border: '2px solid #EF4444',
                            borderRadius: '4px',
                            padding: '16px 24px',
                            marginBottom: '32px'
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#EF4444' }} />
                                <div style={{ flex: 1 }}>
                                    <div style={{ fontSize: '14px', fontWeight: 600, color: '#1C1C1C', marginBottom: '4px' }}>
                                        Error
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#6B5444' }}>{error}</div>
                                </div>
                                    <button
                                        onClick={metadataReady ? handleTryAgain : handleGoToMetadata}
                                        style={{
                                            padding: '8px 16px',
                                            fontSize: '10px',
                                        fontWeight: 'bold',
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.1em',
                                        borderRadius: '4px',
                                        border: '1px solid #EF4444',
                                        backgroundColor: 'white',
                                        color: '#EF4444',
                                        cursor: 'pointer'
                                    }}
                                    >
                                        {metadataReady ? 'Try Again' : 'Go to Metadata'}
                                    </button>
                                </div>
                            </div>
                    )}

                    {currentState === STATE.COMPLETE && (
                        <>
                            <div style={{
                                background: '#FDFCF8',
                                border: '1px solid #EAE3D5',
                                borderRadius: '4px',
                                padding: '48px',
                                marginBottom: '32px'
                            }}>
                                <h1 style={{
                                    fontFamily: "'Crimson Pro', serif",
                                    fontSize: '48px',
                                    fontWeight: 600,
                                    color: '#1C1C1C',
                                    marginBottom: '16px'
                                }}>
                                    Similar Bills
                                </h1>
                                <p style={{ fontSize: '16px', color: '#6B5444', marginBottom: '24px' }}>
                                    {stats.total} bills found with related provisions
                                </p>
                                {similarityStatus && (
                                    <div style={{ fontSize: '12px', color: '#8B7355', marginBottom: '16px' }}>
                                        Status: {similarityStatus}
                                    </div>
                                )}
                                <div style={{ display: 'flex', gap: '16px', fontSize: '14px', color: '#374151' }}>
                                    <span><strong>{stats.passed}</strong> passed</span>
                                    <span style={{ color: '#8B7355' }}>•</span>
                                    <span><strong>{stats.failed}</strong> failed</span>
                                </div>
                            </div>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                {similarBills.map((bill) => (
                                    (() => {
                                        const displayNumber = bill.Bill_Number || `ID ${bill.Bill_ID}`;
                                        const displayTitle = bill.Bill_Title || `Bill ${bill.Bill_ID}`;
                                        return (
                                            <details
                                                key={bill.Bill_ID}
                                                style={{
                                                    background: '#FDFCF8',
                                                    border: '1px solid #EAE3D5',
                                                    borderRadius: '4px',
                                                    padding: '14px 16px'
                                                }}
                                            >
                                                <summary style={{ cursor: 'pointer', listStyle: 'none' }}>
                                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px' }}>
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                                            <span style={{ fontSize: '14px', fontWeight: 600, color: '#1C1C1C' }}>{displayNumber}</span>
                                                            <span style={{ fontSize: '12px', color: '#6B5444' }}>{displayTitle}</span>
                                                            <span style={{
                                                                padding: '3px 8px',
                                                                borderRadius: '4px',
                                                                fontSize: '10px',
                                                                fontWeight: 700,
                                                                textTransform: 'uppercase',
                                                                backgroundColor: bill.Passed ? '#D4EDDA' : '#F8D7DA',
                                                                color: bill.Passed ? '#155724' : '#721C24',
                                                                border: `1px solid ${bill.Passed ? '#C3E6CB' : '#F5C6CB'}`
                                                            }}>
                                                                {bill.Passed ? 'Passed' : 'Failed'}
                                                            </span>
                                                            <span style={{ fontSize: '11px', color: '#8B7355' }}>{formatScore(bill.Score)} match</span>
                                                        </div>
                                                        <span style={{ fontSize: '11px', color: '#8B7355' }}>Click to expand</span>
                                                    </div>
                                                </summary>

                                                <div style={{ marginTop: '12px', borderTop: '1px solid #EAE3D5', paddingTop: '12px' }}>
                                                    <p style={{ fontSize: '13px', color: '#6B5444', lineHeight: '1.6', margin: '0 0 8px 0' }}>
                                                        {bill.Bill_Description || `Similar bill with ${formatScore(bill.Score)} semantic similarity to your legislation.`}
                                                    </p>
                                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
                                                        {bill.Bill_URL && (
                                                            <a
                                                                href={bill.Bill_URL}
                                                                target="_blank"
                                                                rel="noreferrer"
                                                                style={{ fontSize: '12px', color: '#2563EB' }}
                                                            >
                                                                Open official bill page
                                                            </a>
                                                        )}
                                                        <button className="clause-btn clause-btn-secondary" onClick={() => handleInspectBill(bill)}>
                                                            Inspect Bill
                                                        </button>
                                                    </div>
                                                </div>
                                            </details>
                                        );
                                    })()
                                ))}
                            </div>

                            <div style={{ marginTop: '48px' }}>
                                <button
                                    onClick={handleContinue}
                                    className="clause-cta-button"
                                >
                                    Continue to Load Bills
                                </button>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </PageShell>
    );
}

export default SimilarBillsPage;
