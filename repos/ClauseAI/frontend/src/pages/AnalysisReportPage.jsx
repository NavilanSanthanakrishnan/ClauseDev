import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';
import { getWorkflow, updateWorkflow } from '../utils/workflowStorage';
import { setRequestTracking } from '../utils/requestTracking';
import PageShell from '../components/layout/PageShell';
import ToolCallHistoryPanel from '../components/ToolCallHistoryPanel';
import MarkdownRenderer from '../components/MarkdownRenderer';
import BillReportView from '../components/report/BillReportView';
import LegalReportView from '../components/report/LegalReportView';
import StakeholderReportView from '../components/report/StakeholderReportView';
import { ANALYSIS_CONFIG } from '../workflow/analysisConfig';
import { useTwoPhaseAnalysis, TWO_PHASE_STATE } from '../hooks/useTwoPhaseAnalysis';
import { useWorkflowState } from '../hooks/useWorkflowState';

const VIEW_BY_DOMAIN = {
    bill: BillReportView,
    legal: LegalReportView,
    stakeholder: StakeholderReportView
};

const isAcceptedStartResponse = (response) => {
    if (!response) return false;
    if (response.success) return true;
    return response.status === 'running';
};

function AnalysisReportPage({ domain }) {
    const navigate = useNavigate();
    const { workflow } = useWorkflowState();
    const config = ANALYSIS_CONFIG[domain];
    const ViewComponent = VIEW_BY_DOMAIN[domain];

    const hasStartedRef = useRef(false);

    const [reportText, setReportText] = useState('');
    const [structuredData, setStructuredData] = useState(null);
    const [generatedFixes, setGeneratedFixes] = useState([]);
    const [toolHistory, setToolHistory] = useState([]);
    const [currentToolCall, setCurrentToolCall] = useState(null);

    const {
        currentState,
        setCurrentState,
        runReportPhase,
        runFixesPhase,
        progress,
        operation,
        error,
        setError
    } = useTwoPhaseAnalysis({
        report: {
            initialOperation: config?.initialReportOperation,
            start: async () => {
                const workflow = getWorkflow();
                const generatedRequestId = apiService.generateRequestId();
                setRequestTracking(config.trackingKey, generatedRequestId, 'running');

                const response = await config.startReport(workflow, generatedRequestId);
                const effectiveRequestId = response?.request_id || generatedRequestId;
                if (effectiveRequestId !== generatedRequestId) {
                    setRequestTracking(config.trackingKey, effectiveRequestId, 'running');
                }

                if (!isAcceptedStartResponse(response)) {
                    throw new Error(response?.data?.Error || 'Failed to start report phase');
                }

                return { ...response, request_id: effectiveRequestId };
            },
            status: async (requestId) => {
                const status = await config.getReportStatus(requestId);
                const partial = config.parseReportPartial(status);
                if (partial?.reportText) {
                    setReportText(partial.reportText);
                }
                if (config.showToolHistory) {
                    setToolHistory(Array.isArray(partial?.toolHistory) ? partial.toolHistory : []);
                    setCurrentToolCall(partial?.currentToolCall || null);
                }
                return status;
            },
            result: (requestId) => config.getReportResult(requestId),
            onCompleted: (finalData, outcome) => {
                const workflow = getWorkflow();
                if (!finalData || finalData?.Error) {
                    throw new Error(finalData?.Error || 'Report phase completed without data');
                }
                const parsed = config.parseReportResult(workflow, finalData);
                setReportText(parsed.reportText || '');
                setStructuredData(parsed.structuredData || null);
                setGeneratedFixes(parsed.generatedFixes || []);
                updateWorkflow(parsed.workflowPatch || {});
                setRequestTracking(config.trackingKey, outcome.requestId, 'completed');
            },
            onFailed: (outcome) => {
                setRequestTracking(config.trackingKey, outcome?.requestId || null, 'failed');
            }
        },
        fixes: {
            initialOperation: config?.initialFixesOperation,
            start: async () => {
                const workflow = getWorkflow();
                const generatedRequestId = apiService.generateRequestId();
                setRequestTracking(config.trackingKey, generatedRequestId, 'running');
                const response = await config.startFixes(
                    workflow,
                    generatedRequestId,
                    {
                        reportText,
                        structuredData
                    }
                );
                const requestId = response?.request_id || generatedRequestId;
                if (requestId !== generatedRequestId) {
                    setRequestTracking(config.trackingKey, requestId, 'running');
                }

                if (!isAcceptedStartResponse(response)) {
                    throw new Error(response?.data?.Error || 'Failed to start fixes phase');
                }

                return { ...response, request_id: requestId };
            },
            status: async (requestId) => {
                const status = await config.getFixesStatus(requestId);
                const fixesPreview = config.parseFixesPartial(status);
                if (Array.isArray(fixesPreview) && fixesPreview.length > 0) {
                    setGeneratedFixes(fixesPreview);
                }
                return status;
            },
            result: (requestId) => config.getFixesResult(requestId),
            onCompleted: (finalData, outcome) => {
                const workflow = getWorkflow();
                const parsed = config.parseFixesResult(workflow, finalData, {
                    reportText,
                    structuredData
                });
                setGeneratedFixes(parsed.generatedFixes || []);
                updateWorkflow(parsed.workflowPatch || {});
                setRequestTracking(config.trackingKey, outcome.requestId, 'completed');
                updateWorkflow({ currentStep: config.continueRoute });
                navigate(config.continueRoute);
            },
            onFailed: (outcome) => {
                setRequestTracking(config.trackingKey, outcome?.requestId || null, 'failed');
            }
        }
    });

    const runReportPhaseRef = useRef(runReportPhase);
    runReportPhaseRef.current = runReportPhase;

    useEffect(() => {
        if (!config) {
            navigate('/');
            return;
        }

        const currentWorkflow = getWorkflow();

        if (!config.isPrerequisiteMet(currentWorkflow)) {
            navigate(config.prerequisiteRoute);
            return;
        }

        if (currentWorkflow.currentStep !== config.currentStep) {
            updateWorkflow({ currentStep: config.currentStep });
        }

        const savedState = config.parseSavedState(currentWorkflow);
        if (savedState) {
            setReportText(savedState.reportText || '');
            setStructuredData(savedState.structuredData || null);
            setGeneratedFixes(savedState.generatedFixes || []);
            setCurrentState(TWO_PHASE_STATE.REPORT_READY);
            return;
        }

        if (!hasStartedRef.current) {
            hasStartedRef.current = true;
            const tracking = currentWorkflow.requestTracking?.[config.trackingKey];
            if ((tracking?.status === 'running' || tracking?.status === 'completed') && tracking?.requestId) {
                runReportPhaseRef.current({ existingRequestId: tracking.requestId, startIfMissing: false });
            } else {
                runReportPhaseRef.current();
            }
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [config, navigate]);

    const statusLabel = workflow.requestTracking?.[config.trackingKey]?.status;

    const handleContinue = () => {
        updateWorkflow({ currentStep: config.continueRoute });
        navigate(config.continueRoute);
    };

    const handleGenerateFixes = async () => {
        if (!reportText && !structuredData) {
            setError('Report output is required before generating fixes');
            return;
        }
        await runFixesPhase();
    };

    const isRunning = currentState === TWO_PHASE_STATE.ANALYZING_REPORT || currentState === TWO_PHASE_STATE.GENERATING_FIXES;
    const hasProgress = typeof progress === 'number';
    const displayOperation = operation;

    return (
        <PageShell
            title={config.title}
            subtitle={config.subtitle}
            contentMaxWidth={config.contentMaxWidth}
        >
            <div style={{ padding: '8px 0' }}>
                <div style={{ maxWidth: config.contentMaxWidth, margin: '0 auto' }}>
                    {statusLabel && (
                        <div style={{ fontSize: '12px', color: '#8B7355', marginBottom: '12px' }}>
                            Status: {statusLabel}
                        </div>
                    )}

                    {error && (
                        <div className="clause-alert-error" style={{ marginBottom: '32px' }}>
                            <div style={{ fontSize: '12px', color: '#6B5444' }}>{error}</div>
                        </div>
                    )}

                    {isRunning && (
                        <div style={{
                            background: '#FDFCF8',
                            border: '1px solid #EAE3D5',
                            borderRadius: '4px',
                            padding: '32px',
                            marginBottom: '24px'
                        }}>
                                <div className="clause-progress-track" style={{ marginBottom: '12px' }}>
                                <div
                                    className="clause-progress-fill"
                                    style={{
                                        width: `${hasProgress ? progress : 100}%`,
                                        opacity: hasProgress ? 1 : 0.55
                                    }}
                                />
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <p style={{ fontSize: '14px', color: '#6B5444', margin: 0 }}>{displayOperation}</p>
                                <p style={{ fontSize: '12px', color: '#8B7355', margin: 0 }}>
                                    {hasProgress ? `${progress}%` : 'running...'}
                                </p>
                            </div>

                            {domain === 'bill' && reportText && (
                                <div style={{
                                    marginTop: '18px',
                                    background: 'white',
                                    border: '1px solid #EAE3D5',
                                    borderRadius: '4px',
                                    padding: '20px',
                                    maxHeight: '460px',
                                    overflowY: 'auto'
                                }}>
                                    <MarkdownRenderer markdown={reportText} />
                                </div>
                            )}

                            {config.showToolHistory && (
                                <ToolCallHistoryPanel
                                    toolHistory={toolHistory}
                                    currentToolCall={currentToolCall}
                                    title={config.toolCallTitle}
                                />
                            )}
                        </div>
                    )}

                    {currentState === TWO_PHASE_STATE.REPORT_READY && (
                        <>
                            <ViewComponent reportText={reportText} structuredData={structuredData} analysisText={reportText} />

                            <button
                                onClick={generatedFixes.length > 0 ? handleContinue : handleGenerateFixes}
                                className="clause-cta-button"
                            >
                                {generatedFixes.length > 0 ? config.applyFixesLabel : config.generateFixesLabel}
                            </button>
                        </>
                    )}
                </div>
            </div>
        </PageShell>
    );
}

export default AnalysisReportPage;
