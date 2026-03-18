import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    archiveWorkflow,
    deleteWorkflowFromHistory,
    getWorkflowHistory,
    resetWorkflow,
    restoreWorkflowFromHistory,
    updateWorkflow
} from '../utils/workflowStorage';
import PageShell from '../components/layout/PageShell';
import SectionCard from '../components/layout/SectionCard';
import ActionBar from '../components/layout/ActionBar';
import StatusBadge from '../components/layout/StatusBadge';
import { STEP_PATHS, normalizeStepPath } from '../workflow/definitions';
import { useWorkflowState } from '../hooks/useWorkflowState';

const normalizeStep = (step) => normalizeStepPath(step || STEP_PATHS.API_CHECK);

function HomePage() {
    const navigate = useNavigate();
    const { workflow } = useWorkflowState();
    const hasProgress = Boolean(workflow.billText || workflow.metadata?.title || workflow.similarBills?.length);
    const [history, setHistory] = useState(() => getWorkflowHistory());
    const hasHistory = history.length > 0;

    useEffect(() => {
        setHistory(getWorkflowHistory());
    }, [workflow]);

    const handleStart = () => {
        if (hasProgress) {
            archiveWorkflow(workflow, 'start_new');
            setHistory(getWorkflowHistory());
        }
        resetWorkflow();
        updateWorkflow({ currentStep: STEP_PATHS.API_CHECK });
        navigate(STEP_PATHS.API_CHECK);
    };

    const handleResume = () => {
        const nextStep = normalizeStep(workflow.currentStep);
        updateWorkflow({ currentStep: nextStep });
        navigate(nextStep);
    };

    const currentStep = normalizeStep(workflow.currentStep);
    const latestHistory = useMemo(() => history.slice(0, 12), [history]);

    const handleResumeFromHistory = (historyId) => {
        const restored = restoreWorkflowFromHistory(historyId);
        if (!restored) return;
        const nextStep = normalizeStep(restored.currentStep);
        updateWorkflow({ currentStep: nextStep });
        navigate(nextStep);
    };

    const handleDeleteHistory = (historyId) => {
        setHistory(deleteWorkflowFromHistory(historyId));
    };

    return (
        <PageShell
            title="ClauseAI Bill Workflow"
            subtitle="A step-by-step flow for extraction, metadata, analysis, fixes, and export. Workflow state and history are saved to Supabase."
            contentMaxWidth="980px"
        >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <SectionCard
                    title="Session Status"
                    subtitle="Continue from your latest stage or start a clean run."
                    actions={<StatusBadge value={hasProgress ? 'running' : 'idle'} />}
                >
                    <div className="clause-centered-stack">
                        <div style={{ fontSize: '13px', color: '#6B5444' }}>
                            Current saved step: <strong>{currentStep}</strong>
                        </div>
                        <ActionBar style={{ justifyContent: 'center' }}>
                            <button onClick={handleStart} className="clause-btn clause-btn-primary">
                                Start New Workflow
                            </button>
                            {hasProgress && (
                                <button onClick={handleResume} className="clause-btn clause-btn-secondary">
                                    Resume Last Step
                                </button>
                            )}
                        </ActionBar>
                    </div>
                </SectionCard>

                {hasHistory && (
                    <SectionCard title="Saved Workflows" subtitle="Reopen previous runs from your Supabase workflow history.">
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            {latestHistory.map((entry) => (
                                <details
                                    key={entry.id}
                                    style={{
                                        border: '1px solid #EAE3D5',
                                        borderRadius: '4px',
                                        background: '#fff',
                                        padding: '10px 12px'
                                    }}
                                >
                                    <summary style={{ cursor: 'pointer', listStyle: 'none' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'center' }}>
                                            <div style={{ fontSize: '13px', color: '#1C1C1C', fontWeight: 600 }}>
                                                {entry.title}
                                            </div>
                                            <div style={{ fontSize: '11px', color: '#8B7355' }}>
                                                {new Date(entry.savedAt).toLocaleString()}
                                            </div>
                                        </div>
                                    </summary>

                                    <div style={{ marginTop: '8px', borderTop: '1px solid #EAE3D5', paddingTop: '8px' }}>
                                        <div style={{ fontSize: '12px', color: '#6B5444', marginBottom: '8px' }}>
                                            Last step: <strong>{normalizeStep(entry.currentStep)}</strong>
                                        </div>
                                        <ActionBar>
                                            <button className="clause-btn clause-btn-secondary" onClick={() => handleResumeFromHistory(entry.id)}>
                                                Open Workflow
                                            </button>
                                            <button className="clause-btn clause-btn-soft" onClick={() => handleDeleteHistory(entry.id)}>
                                                Remove
                                            </button>
                                        </ActionBar>
                                    </div>
                                </details>
                            ))}
                        </div>
                    </SectionCard>
                )}
            </div>
        </PageShell>
    );
}

export default HomePage;
