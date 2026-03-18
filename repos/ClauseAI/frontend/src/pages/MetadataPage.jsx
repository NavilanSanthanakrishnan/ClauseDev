import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';
import { updateWorkflow } from '../utils/workflowStorage';
import { setRequestTracking } from '../utils/requestTracking';
import PageShell from '../components/layout/PageShell';
import { STEP_PATHS } from '../workflow/definitions';
import { useWorkflowState } from '../hooks/useWorkflowState';

const LAST_EXTRACTION_KEY = 'clauseai.last_extraction.v1';

const readLastExtraction = () => {
    if (typeof window === 'undefined') return null;
    try {
        const raw = window.localStorage.getItem(LAST_EXTRACTION_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed?.text !== 'string' || parsed.text.trim().length === 0) {
            return null;
        }
        return parsed;
    } catch {
        return null;
    }
};

const STATE = {
    LOADING: 'loading',
    COMPLETE: 'complete',
    ERROR: 'error'
};

function MetadataPage() {
    const navigate = useNavigate();
    const { workflow } = useWorkflowState();
    const hasStartedRef = useRef(false);
    const [cachedExtraction] = useState(() => readLastExtraction());
    const [currentState, setCurrentState] = useState(STATE.LOADING);
    const [metadata, setMetadata] = useState({ title: '', description: '', summary: '' });
    const [error, setError] = useState(null);
    const metadataStatus = workflow.requestTracking?.metadata?.status;
    const workflowMetadata = {
        title: workflow.metadata?.title ?? workflow.metadata?.Title ?? '',
        description: workflow.metadata?.description ?? workflow.metadata?.Description ?? '',
        summary: workflow.metadata?.summary ?? workflow.metadata?.Summary ?? ''
    };
    const hasRequiredMetadata = (
        metadata.title?.trim().length > 0 &&
        metadata.description?.trim().length > 0
    );
    const effectiveBillText = (
        workflow.extraction?.editedText ||
        workflow.billText ||
        cachedExtraction?.text ||
        ''
    );

    useEffect(() => {
        const liveText = workflow.extraction?.editedText || workflow.billText || '';
        if (!liveText && cachedExtraction?.text) {
            updateWorkflow({
                billText: cachedExtraction.text,
                extraction: {
                    originalText: workflow.extraction?.originalText || cachedExtraction.text,
                    editedText: cachedExtraction.text,
                    stats: workflow.extraction?.stats || cachedExtraction.stats || null,
                    fileName: workflow.extraction?.fileName || cachedExtraction.fileName || '',
                    fileSize: workflow.extraction?.fileSize || cachedExtraction.fileSize || 0,
                    fileType: workflow.extraction?.fileType || cachedExtraction.fileType || ''
                }
            });
        }

        if (!effectiveBillText) {
            navigate(STEP_PATHS.EXTRACTION_INPUT);
            return;
        }

        if (workflow.currentStep !== STEP_PATHS.METADATA) {
            updateWorkflow({ currentStep: STEP_PATHS.METADATA });
        }

        if (workflowMetadata.title || workflowMetadata.description || workflowMetadata.summary) {
            setMetadata({
                title: workflowMetadata.title || '',
                description: workflowMetadata.description || '',
                summary: workflowMetadata.summary || ''
            });
            setCurrentState(STATE.COMPLETE);
            return;
        }

        if (!hasStartedRef.current) {
            hasStartedRef.current = true;
            generateMetadata();
        }
    }, [
        navigate,
        workflow.billText,
        workflow.currentStep,
        workflow.extraction?.editedText,
        workflow.metadata?.description,
        workflow.metadata?.summary,
        workflow.metadata?.title,
        workflow.metadata?.Description,
        workflow.metadata?.Summary,
        workflow.metadata?.Title,
        workflow.billText,
        cachedExtraction,
        effectiveBillText
    ]);

    const generateMetadata = async () => {
        setCurrentState(STATE.LOADING);
        setError(null);

        let requestId = null;
        try {
            requestId = apiService.generateRequestId();
            setRequestTracking('metadata', requestId, 'running');
            const response = await apiService.generateMetadata(effectiveBillText, requestId);

            if (response.success) {
                const metadataResult = {
                    title: response.data.Title || '',
                    description: response.data.Description || '',
                    summary: response.data.Summary || ''
                };

                setMetadata(metadataResult);
                updateWorkflow({
                    metadata: {
                        ...metadataResult,
                        processingTime: response.processing_time
                    }
                });
                setRequestTracking('metadata', requestId, 'completed');
                setCurrentState(STATE.COMPLETE);
            } else {
                const errorMessage = response.data?.Error || 'Failed to generate metadata';
                setError(errorMessage);
                setRequestTracking('metadata', requestId, 'failed');
                setCurrentState(STATE.ERROR);
            }
        } catch (err) {
            setError(err.message || 'Failed to generate metadata');
            setRequestTracking('metadata', null, 'failed');
            setCurrentState(STATE.ERROR);
        }
    };

    const handleChange = (field, value) => {
        const next = { ...metadata, [field]: value };
        setMetadata(next);
        if (error) {
            setError(null);
        }
        updateWorkflow({
            metadata: {
                ...workflowMetadata,
                ...next
            }
        });
    };

    const handleContinue = () => {
        if (!hasRequiredMetadata) {
            setError('Title and description are required before continuing.');
            return;
        }
        const normalizedSummary = metadata.summary?.trim() ? metadata.summary : metadata.description;
        const nextMetadata = {
            ...workflowMetadata,
            ...metadata,
            summary: normalizedSummary
        };
        setMetadata(nextMetadata);
        updateWorkflow({ metadata: nextMetadata });
        updateWorkflow({ currentStep: STEP_PATHS.SIMILAR_BILLS });
        navigate(STEP_PATHS.SIMILAR_BILLS);
    };

    const handleTryAgain = () => {
        hasStartedRef.current = false;
        generateMetadata();
    };

    return (
        <PageShell>
            <div style={{ padding: '8px 0' }}>
                <div style={{ maxWidth: '900px', margin: '0 auto' }}>
                    <div style={{
                        background: '#FDFCF8',
                        border: '1px solid #EAE3D5',
                        borderRadius: '4px',
                        padding: '48px'
                    }}>
                        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
                            <h1 style={{
                                fontFamily: "'Crimson Pro', serif",
                                fontSize: '48px',
                                fontWeight: 600,
                                color: '#1C1C1C',
                                margin: '0 0 16px 0'
                            }}>
                                Bill Metadata
                            </h1>
                            <p style={{ color: '#6B5444', fontSize: '16px', fontStyle: 'italic' }}>
                                Review and edit title, description, and summary.
                            </p>
                            {metadataStatus && (
                                <div style={{ fontSize: '12px', color: '#8B7355', marginTop: '12px' }}>
                                    Status: {metadataStatus}
                                </div>
                            )}
                        </div>

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
                                        onClick={handleTryAgain}
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
                                        Try Again
                                    </button>
                                </div>
                            </div>
                        )}

                        {currentState === STATE.LOADING && (
                            <div style={{ marginBottom: '40px' }}>
                                <div style={{ marginBottom: '32px' }}>
                                    <div style={{
                                        fontSize: '10px',
                                        fontWeight: 'bold',
                                        letterSpacing: '0.3em',
                                        textTransform: 'uppercase',
                                        color: '#8B7355',
                                        marginBottom: '12px'
                                    }}>
                                        TITLE
                                    </div>
                                    <div className="clause-skeleton" style={{ width: '60%', height: '48px', borderRadius: '4px' }} />
                                </div>

                                <div style={{ marginBottom: '32px' }}>
                                    <div style={{
                                        fontSize: '10px',
                                        fontWeight: 'bold',
                                        letterSpacing: '0.3em',
                                        textTransform: 'uppercase',
                                        color: '#8B7355',
                                        marginBottom: '12px'
                                    }}>
                                        DESCRIPTION
                                    </div>
                                    <div className="clause-skeleton" style={{ width: '100%', height: '80px', borderRadius: '4px' }} />
                                </div>

                                <div>
                                    <div style={{
                                        fontSize: '10px',
                                        fontWeight: 'bold',
                                        letterSpacing: '0.3em',
                                        textTransform: 'uppercase',
                                        color: '#8B7355',
                                        marginBottom: '12px'
                                    }}>
                                        SUMMARY
                                    </div>
                                    <div className="clause-skeleton" style={{ width: '100%', height: '150px', borderRadius: '4px' }} />
                                </div>
                            </div>
                        )}

                        {currentState === STATE.COMPLETE && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                                <div>
                                    <label style={{
                                        fontSize: '10px',
                                        fontWeight: 'bold',
                                        letterSpacing: '0.3em',
                                        textTransform: 'uppercase',
                                        color: '#8B7355',
                                        display: 'block',
                                        marginBottom: '8px'
                                    }}>
                                        Title
                                    </label>
                                    <input
                                        value={metadata.title}
                                        onChange={(e) => handleChange('title', e.target.value)}
                                        style={{
                                            width: '100%',
                                            padding: '12px 14px',
                                            borderRadius: '4px',
                                            border: '1px solid #EAE3D5',
                                            fontSize: '16px',
                                            fontFamily: "'Crimson Pro', serif"
                                        }}
                                    />
                                </div>

                                <div>
                                    <label style={{
                                        fontSize: '10px',
                                        fontWeight: 'bold',
                                        letterSpacing: '0.3em',
                                        textTransform: 'uppercase',
                                        color: '#8B7355',
                                        display: 'block',
                                        marginBottom: '8px'
                                    }}>
                                        Description
                                    </label>
                                    <textarea
                                        value={metadata.description}
                                        onChange={(e) => handleChange('description', e.target.value)}
                                        style={{
                                            width: '100%',
                                            minHeight: '120px',
                                            padding: '12px 14px',
                                            borderRadius: '4px',
                                            border: '1px solid #EAE3D5',
                                            fontSize: '14px',
                                            fontFamily: "'Inter', sans-serif",
                                            lineHeight: '1.6',
                                            resize: 'vertical'
                                        }}
                                    />
                                </div>

                                <div>
                                    <label style={{
                                        fontSize: '10px',
                                        fontWeight: 'bold',
                                        letterSpacing: '0.3em',
                                        textTransform: 'uppercase',
                                        color: '#8B7355',
                                        display: 'block',
                                        marginBottom: '8px'
                                    }}>
                                        Summary
                                    </label>
                                    <textarea
                                        value={metadata.summary}
                                        onChange={(e) => handleChange('summary', e.target.value)}
                                        style={{
                                            width: '100%',
                                            minHeight: '180px',
                                            padding: '12px 14px',
                                            borderRadius: '4px',
                                            border: '1px solid #EAE3D5',
                                            fontSize: '14px',
                                            fontFamily: "'Crimson Pro', serif",
                                            lineHeight: '1.7',
                                            resize: 'vertical'
                                        }}
                                    />
                                </div>
                            </div>
                        )}

                        {currentState === STATE.COMPLETE && (
                            <div style={{ marginTop: '32px' }}>
                                <button
                                    onClick={handleContinue}
                                    disabled={!hasRequiredMetadata}
                                    className="clause-cta-button"
                                >
                                    Find Similar Bills
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </PageShell>
    );
}

export default MetadataPage;
