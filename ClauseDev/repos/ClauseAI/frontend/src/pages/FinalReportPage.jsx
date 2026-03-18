import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { updateWorkflow } from '../utils/workflowStorage';
import PageShell from '../components/layout/PageShell';
import { normalizeFixClassificationPayload } from '../utils/fixMapping';
import { extractOptimizations } from '../utils/fixChangeApplicator';
import { STEP_PATHS } from '../workflow/definitions';
import { useWorkflowState } from '../hooks/useWorkflowState';

const RISK_COLORS = {
    HIGH: '#DC3545',
    MEDIUM: '#FFC107',
    LOW: '#28A745'
};

function FinalReportPage() {
    const navigate = useNavigate();
    const { workflow } = useWorkflowState();

    useEffect(() => {
        if (!workflow.stakeholderAnalysis?.structuredData) {
            navigate(STEP_PATHS.STAKEHOLDER_FIXES);
            return;
        }
        if (workflow.currentStep !== STEP_PATHS.FINAL_REPORT || !workflow.finalReport?.generatedAt) {
            updateWorkflow({
                currentStep: STEP_PATHS.FINAL_REPORT,
                finalReport: {
                    generatedAt: workflow.finalReport?.generatedAt || new Date().toISOString()
                }
            });
        }
    }, [
        navigate,
        workflow.currentStep,
        workflow.finalReport?.generatedAt,
        workflow.stakeholderAnalysis?.structuredData
    ]);

    const billImprovements = normalizeFixClassificationPayload(
        workflow.billAnalysis,
        workflow.billAnalysis?.directImprovements || []
    ).validImprovements;
    const legalImprovements = normalizeFixClassificationPayload(
        workflow.legalAnalysis,
        workflow.legalAnalysis?.structuredData?.legal_improvements || []
    ).validImprovements;
    const stakeholderOptimizations = normalizeFixClassificationPayload(
        workflow.stakeholderAnalysis,
        extractOptimizations(workflow.stakeholderAnalysis?.structuredData || {})
    ).validImprovements;

    const appliedBillFixes = workflow.billFixes?.appliedOrder || [];
    const appliedLegalFixes = workflow.legalFixes?.appliedOrder || [];
    const appliedStakeholderFixes = workflow.stakeholderFixes?.appliedOrder || [];

    const getRiskBadgeStyle = (riskLevel) => {
        const color = RISK_COLORS[riskLevel] || '#6C757D';
        return {
            padding: '4px 12px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 700,
            textTransform: 'uppercase',
            backgroundColor: color + '20',
            color: color,
            border: `1px solid ${color}`
        };
    };

    const handleContinue = () => {
        updateWorkflow({ currentStep: STEP_PATHS.FINAL_EDITING });
        navigate(STEP_PATHS.FINAL_EDITING);
    };

    return (
        <PageShell>
            <div style={{ padding: '8px 0' }}>
                <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
                    <div style={{
                        background: '#FDFCF8',
                        border: '1px solid #EAE3D5',
                        borderRadius: '4px',
                        padding: '32px',
                        marginBottom: '24px'
                    }}>
                        <h1 style={{
                            fontFamily: "'Crimson Pro', serif",
                            fontSize: '44px',
                            fontWeight: 600,
                            color: '#1C1C1C',
                            marginBottom: '16px'
                        }}>
                            Final Report
                        </h1>
                        <p style={{ fontSize: '15px', color: '#6B5444' }}>
                            Combined analysis and applied changes. All data is reconstructed from Supabase-backed workflow state.
                        </p>
                    </div>

                    <div style={{
                        background: 'white',
                        border: '1px solid #EAE3D5',
                        borderRadius: '4px',
                        padding: '24px',
                        marginBottom: '24px'
                    }}>
                        <h2 style={{
                            fontFamily: "'Crimson Pro', serif",
                            fontSize: '28px',
                            fontWeight: 600,
                            color: '#1C1C1C',
                            marginBottom: '16px'
                        }}>
                            Metadata
                        </h2>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <div style={{ fontSize: '14px', color: '#1C1C1C' }}>
                                <strong>Title:</strong> {workflow.metadata?.title}
                            </div>
                            <div style={{ fontSize: '14px', color: '#1C1C1C' }}>
                                <strong>Description:</strong> {workflow.metadata?.description}
                            </div>
                            <div style={{ fontSize: '14px', color: '#1C1C1C' }}>
                                <strong>Summary:</strong> {workflow.metadata?.summary}
                            </div>
                        </div>
                    </div>

                    <div style={{
                        background: 'white',
                        border: '1px solid #EAE3D5',
                        borderRadius: '4px',
                        padding: '24px',
                        marginBottom: '24px'
                    }}>
                        <h2 style={{
                            fontFamily: "'Crimson Pro', serif",
                            fontSize: '28px',
                            fontWeight: 600,
                            color: '#1C1C1C',
                            marginBottom: '16px'
                        }}>
                            Bill Analysis Report
                        </h2>
                        <div style={{ fontSize: '13px', color: '#6B5444', lineHeight: '1.7', whiteSpace: 'pre-wrap' }}>
                            {workflow.billAnalysis?.report}
                        </div>
                        <div style={{ marginTop: '16px', fontSize: '12px', color: '#8B7355' }}>
                            Applied fixes: {appliedBillFixes.length} of {billImprovements.length}
                        </div>
                        {appliedBillFixes.length > 0 && (
                            <div style={{ marginTop: '12px' }}>
                                <div style={{ fontSize: '12px', fontWeight: 600, color: '#1C1C1C', marginBottom: '8px' }}>
                                    Applied Bill Improvements
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    {appliedBillFixes.map((idx) => {
                                        const improvement = billImprovements[idx];
                                        return (
                                            <div key={idx} style={{ fontSize: '12px', color: '#6B5444' }}>
                                                {improvement?.metadata?.short_explanation || improvement?.short_explanation || `Improvement ${idx + 1}`}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                    </div>

                    <div style={{
                        background: 'white',
                        border: '1px solid #EAE3D5',
                        borderRadius: '4px',
                        padding: '24px',
                        marginBottom: '24px'
                    }}>
                        <h2 style={{
                            fontFamily: "'Crimson Pro', serif",
                            fontSize: '28px',
                            fontWeight: 600,
                            color: '#1C1C1C',
                            marginBottom: '16px'
                        }}>
                            Legal Conflicts
                        </h2>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                            {(workflow.legalAnalysis?.structuredData?.external_conflicts || []).map((conflict, idx) => (
                                <div key={idx} style={{
                                    background: '#FDFCF8',
                                    border: '1px solid #EAE3D5',
                                    borderLeft: `4px solid ${RISK_COLORS[conflict.risk_level]}`,
                                    borderRadius: '4px',
                                    padding: '16px'
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                        <div style={{ fontSize: '14px', fontWeight: 600, color: '#1C1C1C' }}>
                                            {conflict.conflicting_statute}
                                        </div>
                                        <span style={getRiskBadgeStyle(conflict.risk_level)}>{conflict.risk_level}</span>
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#6B5444', lineHeight: '1.6' }}>{conflict.explanation}</div>
                                </div>
                            ))}
                        </div>
                        <div style={{ marginTop: '16px', fontSize: '12px', color: '#8B7355' }}>
                            Applied legal fixes: {appliedLegalFixes.length} of {legalImprovements.length}
                        </div>
                        {appliedLegalFixes.length > 0 && (
                            <div style={{ marginTop: '12px' }}>
                                <div style={{ fontSize: '12px', fontWeight: 600, color: '#1C1C1C', marginBottom: '8px' }}>
                                    Applied Legal Improvements
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    {appliedLegalFixes.map((idx) => {
                                        const improvement = legalImprovements[idx];
                                        return (
                                            <div key={idx} style={{ fontSize: '12px', color: '#6B5444' }}>
                                                {improvement?.short_explanation || improvement?.explanation || `Improvement ${idx + 1}`}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                    </div>

                    <div style={{
                        background: 'white',
                        border: '1px solid #EAE3D5',
                        borderRadius: '4px',
                        padding: '24px',
                        marginBottom: '24px'
                    }}>
                        <h2 style={{
                            fontFamily: "'Crimson Pro', serif",
                            fontSize: '28px',
                            fontWeight: 600,
                            color: '#1C1C1C',
                            marginBottom: '16px'
                        }}>
                            Stakeholder Analysis
                        </h2>
                        <div style={{ fontSize: '12px', color: '#6B5444', lineHeight: '1.7' }}>
                            Industries analyzed: {workflow.stakeholderAnalysis?.structuredData?.stakeholder_analysis?.affected_industries?.length || 0}
                        </div>
                        <div style={{ marginTop: '12px', fontSize: '12px', color: '#8B7355' }}>
                            Applied stakeholder fixes: {appliedStakeholderFixes.length} of {stakeholderOptimizations.length}
                        </div>
                        {appliedStakeholderFixes.length > 0 && (
                            <div style={{ marginTop: '12px' }}>
                                <div style={{ fontSize: '12px', fontWeight: 600, color: '#1C1C1C', marginBottom: '8px' }}>
                                    Applied Stakeholder Optimizations
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    {appliedStakeholderFixes.map((idx) => {
                                        const improvement = stakeholderOptimizations[idx];
                                        return (
                                            <div key={idx} style={{ fontSize: '12px', color: '#6B5444' }}>
                                                {improvement?.short_explanation || improvement?.summary || improvement?.title || `Optimization ${idx + 1}`}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                        {appliedStakeholderFixes.length > 0 && stakeholderOptimizations.length === 0 && (
                            <div style={{ marginTop: '12px', fontSize: '12px', color: '#6B5444' }}>
                                Applied stakeholder fixes were recorded, but no detailed optimization text was returned from the analysis.
                            </div>
                        )}
                    </div>

                    <div style={{
                        background: '#FDFCF8',
                        border: '1px solid #EAE3D5',
                        borderRadius: '4px',
                        padding: '24px',
                        marginBottom: '24px'
                    }}>
                        <h2 style={{
                            fontFamily: "'Crimson Pro', serif",
                            fontSize: '28px',
                            fontWeight: 600,
                            color: '#1C1C1C',
                            marginBottom: '16px'
                        }}>
                            Final Bill Text
                        </h2>
                        <div style={{
                            background: 'white',
                            border: '1px solid #EAE3D5',
                            borderRadius: '4px',
                            padding: '16px',
                            maxHeight: '480px',
                            overflowY: 'auto',
                            fontFamily: 'monospace',
                            fontSize: '12px',
                            whiteSpace: 'pre-wrap',
                            lineHeight: '1.7'
                        }}>
                            {workflow.billText}
                        </div>
                    </div>

                    <button
                        onClick={handleContinue}
                        className="clause-cta-button"
                    >
                        Continue to Final Editing
                    </button>
                </div>
            </div>
        </PageShell>
    );
}

export default FinalReportPage;
