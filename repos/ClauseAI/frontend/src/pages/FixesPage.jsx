import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { resetStepByPath, updateWorkflow } from '../utils/workflowStorage';
import { renderHighlightedText } from '../utils/textFormatting';
import { applyChange, revertChange } from '../utils/fixChangeApplicator';
import PageShell from '../components/layout/PageShell';
import { FIXES_CONFIG } from '../workflow/fixesConfig';
import { useWorkflowState } from '../hooks/useWorkflowState';

function FixesPage({ domain }) {
    const navigate = useNavigate();
    const { workflow } = useWorkflowState();
    const config = FIXES_CONFIG[domain];

    const [billText, setBillText] = useState('');
    const [appliedSet, setAppliedSet] = useState(new Set());
    const [appliedOrder, setAppliedOrder] = useState([]);
    const [highlight, setHighlight] = useState(null);
    const [toast, setToast] = useState(null);
    const [itemErrors, setItemErrors] = useState({});
    const [expanded, setExpanded] = useState(new Set());

    const classification = useMemo(() => {
        return config.classify(workflow);
    }, [config, workflow]);

    const improvements = classification.validImprovements;
    const invalidImprovements = classification.invalidImprovements;

    useEffect(() => {
        if (!config) {
            navigate('/');
            return;
        }

        const savedClassification = config.classify(workflow);
        const savedImprovements = savedClassification.validImprovements;
        const savedInvalidImprovements = savedClassification.invalidImprovements;
        if (savedImprovements.length === 0 && savedInvalidImprovements.length === 0) {
            navigate(config.fallbackRoute);
            return;
        }

        updateWorkflow({ currentStep: config.currentStep });

        const fixes = workflow[config.workflowKey];
        const startingText = fixes?.billText || workflow.billText;
        setBillText(startingText || '');
        setAppliedOrder(fixes?.appliedOrder || []);
        setAppliedSet(new Set(fixes?.appliedSet || []));
        setHighlight(fixes?.lastApplied?.highlight || null);
        setItemErrors(fixes?.itemErrors || {});
    }, [config, navigate, workflow]);

    const persistFixes = (next) => {
        updateWorkflow({
            billText: next.billText,
            [config.workflowKey]: {
                billText: next.billText,
                history: [],
                appliedOrder: next.appliedOrder,
                appliedSet: Array.from(next.appliedSet),
                lastApplied: next.lastApplied,
                itemErrors: next.itemErrors
            }
        });
    };

    const setItemError = (index, message) => {
        setItemErrors((prev) => ({ ...prev, [index]: message }));
    };

    const clearItemError = (index) => {
        setItemErrors((prev) => {
            const next = { ...prev };
            delete next[index];
            return next;
        });
    };

    const applyImprovement = (index) => {
        if (appliedSet.has(index)) return;
        const improvement = improvements[index];

        try {
            const result = applyChange(billText, improvement);
            const nextAppliedOrder = [...appliedOrder, index];
            const nextAppliedSet = new Set([...appliedSet, index]);

            clearItemError(index);
            setBillText(result.updatedText);
            setAppliedOrder(nextAppliedOrder);
            setAppliedSet(nextAppliedSet);
            setHighlight(result.highlight);
            setToast(config.applyToast(index));

            persistFixes({
                billText: result.updatedText,
                appliedOrder: nextAppliedOrder,
                appliedSet: nextAppliedSet,
                lastApplied: { index, highlight: result.highlight, timestamp: Date.now() },
                itemErrors: { ...itemErrors, [index]: undefined }
            });

            setTimeout(() => setToast(null), 1800);
        } catch (error) {
            const message = error.message || config.applyErrorFallback;
            setItemError(index, message);
            persistFixes({
                billText,
                appliedOrder,
                appliedSet,
                lastApplied: null,
                itemErrors: { ...itemErrors, [index]: message }
            });
        }
    };

    const revertImprovement = (index) => {
        if (!appliedSet.has(index)) return;
        const improvement = improvements[index];

        try {
            const result = revertChange(billText, improvement);
            const nextAppliedOrder = appliedOrder.filter((value) => value !== index);
            const nextAppliedSet = new Set(nextAppliedOrder);

            clearItemError(index);
            setBillText(result.updatedText);
            setAppliedOrder(nextAppliedOrder);
            setAppliedSet(nextAppliedSet);
            setHighlight(result.highlight);
            setToast(config.revertToast(index));

            persistFixes({
                billText: result.updatedText,
                appliedOrder: nextAppliedOrder,
                appliedSet: nextAppliedSet,
                lastApplied: { index, highlight: result.highlight, timestamp: Date.now() },
                itemErrors: { ...itemErrors, [index]: undefined }
            });

            setTimeout(() => setToast(null), 1800);
        } catch (error) {
            const message = error.message || config.revertErrorFallback;
            setItemError(index, message);
            persistFixes({
                billText,
                appliedOrder,
                appliedSet,
                lastApplied: null,
                itemErrors: { ...itemErrors, [index]: message }
            });
        }
    };

    const toggleExpanded = (key) => {
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(key)) {
                next.delete(key);
            } else {
                next.add(key);
            }
            return next;
        });
    };

    const handleContinue = () => {
        // Moving forward from a fixes step should always invalidate downstream analysis
        // so the next stage is recomputed from the latest edited bill text.
        resetStepByPath(config.continueRoute);
        navigate(config.continueRoute);
    };

    if (!config) return null;

    return (
        <PageShell
            title={config.title}
            subtitle={config.subtitle}
            contentMaxWidth="1400px"
        >
            <div style={{ padding: '8px 0' }}>
                <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                        <div style={{
                            background: '#FDFCF8',
                            border: '1px solid #EAE3D5',
                            borderRadius: '4px',
                            padding: '20px',
                            display: 'flex',
                            flexDirection: 'column',
                            minHeight: '520px'
                        }}>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: '#8B7355', textTransform: 'uppercase', marginBottom: '12px' }}>
                                Bill Text
                            </div>
                            <div style={{
                                flex: 1,
                                border: '1px solid #EAE3D5',
                                borderRadius: '4px',
                                padding: '16px',
                                background: 'white',
                                fontFamily: 'monospace',
                                fontSize: '12px',
                                lineHeight: '1.7',
                                color: '#1C1C1C',
                                overflowY: 'auto',
                                whiteSpace: 'pre-wrap'
                            }}>
                                {renderHighlightedText(billText, highlight)}
                            </div>
                        </div>

                        <div style={{
                            background: '#FDFCF8',
                            border: '1px solid #EAE3D5',
                            borderRadius: '4px',
                            padding: '20px',
                            minHeight: '520px',
                            overflowY: 'auto'
                        }}>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: '#8B7355', textTransform: 'uppercase', marginBottom: '12px' }}>
                                {config.improvementsLabel}
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                {improvements.map((improvement, idx) => {
                                    const isApplied = appliedSet.has(idx);
                                    const title = config.titleResolver(improvement, idx);
                                    const rationale = config.rationaleResolver(improvement, idx);
                                    const sectionLabel = config.sectionResolver(improvement, idx);
                                    const expansionKey = `valid-${idx}`;
                                    const isExpanded = expanded.has(expansionKey);
                                    const itemError = itemErrors[idx];

                                    return (
                                        <div key={idx} style={{
                                            border: `2px solid ${isApplied ? '#C8E6C9' : '#EAE3D5'}`,
                                            borderRadius: '4px',
                                            padding: '16px',
                                            background: isApplied ? '#F1F8F4' : 'white'
                                        }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                                <div style={{ fontSize: '11px', fontWeight: 600, color: '#8B7355' }}>
                                                    {sectionLabel}
                                                </div>
                                                <div style={{ fontSize: '10px', color: '#8B7355' }}>
                                                    {isApplied ? 'Applied' : 'Pending'}
                                                </div>
                                            </div>
                                            <div style={{ fontSize: '13px', fontWeight: 600, color: '#1C1C1C', marginBottom: '6px' }}>
                                                {title}
                                            </div>
                                            <div style={{ fontSize: '12px', color: '#6B5444', lineHeight: '1.6', marginBottom: '12px' }}>
                                                {rationale}
                                            </div>

                                            <button
                                                onClick={() => toggleExpanded(expansionKey)}
                                                style={{
                                                    width: '100%',
                                                    marginBottom: '10px',
                                                    padding: '8px 10px',
                                                    fontSize: '10px',
                                                    fontWeight: 'bold',
                                                    textTransform: 'uppercase',
                                                    letterSpacing: '0.1em',
                                                    borderRadius: '4px',
                                                    border: '1px solid #D5C4AA',
                                                    backgroundColor: '#F7F2E8',
                                                    color: '#5A4A3B',
                                                    cursor: 'pointer'
                                                }}
                                            >
                                                {isExpanded ? 'Hide Diff' : 'View Diff'}
                                            </button>

                                            {isExpanded && (
                                                <pre style={{
                                                    margin: '0 0 10px 0',
                                                    background: '#111827',
                                                    color: '#E5E7EB',
                                                    borderRadius: '4px',
                                                    padding: '12px',
                                                    fontSize: '11px',
                                                    lineHeight: '1.5',
                                                    overflowX: 'auto',
                                                    whiteSpace: 'pre'
                                                }}>
                                                    {improvement?.change || ''}
                                                </pre>
                                            )}

                                            {itemError && (
                                                <div style={{
                                                    marginBottom: '10px',
                                                    padding: '8px 10px',
                                                    borderRadius: '4px',
                                                    border: '1px solid #F5C3BE',
                                                    background: '#FEF2F2',
                                                    color: '#B42318',
                                                    fontSize: '11px'
                                                }}>
                                                    {itemError}
                                                </div>
                                            )}

                                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                                                <button
                                                    onClick={() => applyImprovement(idx)}
                                                    disabled={isApplied}
                                                    style={{
                                                        padding: '10px 12px',
                                                        fontSize: '10px',
                                                        fontWeight: 'bold',
                                                        textTransform: 'uppercase',
                                                        letterSpacing: '0.12em',
                                                        borderRadius: '4px',
                                                        border: 'none',
                                                        backgroundColor: isApplied ? '#C8E6C9' : '#1C1C1C',
                                                        color: isApplied ? '#2E7D32' : '#FDFCF8',
                                                        cursor: isApplied ? 'not-allowed' : 'pointer'
                                                    }}
                                                >
                                                    Apply
                                                </button>
                                                <button
                                                    onClick={() => revertImprovement(idx)}
                                                    disabled={!isApplied}
                                                    style={{
                                                        padding: '10px 12px',
                                                        fontSize: '10px',
                                                        fontWeight: 'bold',
                                                        textTransform: 'uppercase',
                                                        letterSpacing: '0.12em',
                                                        borderRadius: '4px',
                                                        border: '1px solid #1C1C1C',
                                                        backgroundColor: !isApplied ? '#F3F4F6' : '#FFFFFF',
                                                        color: '#1C1C1C',
                                                        cursor: !isApplied ? 'not-allowed' : 'pointer'
                                                    }}
                                                >
                                                    Revert
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })}

                                {invalidImprovements.length > 0 && (
                                    <div style={{
                                        marginTop: '8px',
                                        borderTop: '1px solid #EAE3D5',
                                        paddingTop: '16px',
                                        display: 'flex',
                                        flexDirection: 'column',
                                        gap: '10px'
                                    }}>
                                        <div style={{ fontSize: '12px', fontWeight: 700, color: '#B42318', textTransform: 'uppercase' }}>
                                            Invalid Patches
                                        </div>
                                        {invalidImprovements.map((entry, idx) => {
                                            const item = entry?.item || {};
                                            const reason = entry?.reason || 'Patch format is invalid';
                                            const title = config.invalidTitleResolver(item, idx);
                                            const expansionKey = `invalid-${idx}`;
                                            const isExpanded = expanded.has(expansionKey);

                                            return (
                                                <div key={expansionKey} style={{
                                                    border: '2px solid #F5C3BE',
                                                    borderRadius: '4px',
                                                    padding: '14px',
                                                    background: '#FEF2F2'
                                                }}>
                                                    <div style={{ fontSize: '12px', fontWeight: 600, color: '#7A271A', marginBottom: '6px' }}>
                                                        {title}
                                                    </div>
                                                    <div style={{
                                                        marginBottom: '10px',
                                                        padding: '8px 10px',
                                                        borderRadius: '4px',
                                                        border: '1px solid #F5C3BE',
                                                        background: '#FFF5F4',
                                                        color: '#B42318',
                                                        fontSize: '11px'
                                                    }}>
                                                        {reason}
                                                    </div>
                                                    <button
                                                        onClick={() => toggleExpanded(expansionKey)}
                                                        style={{
                                                            width: '100%',
                                                            marginBottom: '10px',
                                                            padding: '8px 10px',
                                                            fontSize: '10px',
                                                            fontWeight: 'bold',
                                                            textTransform: 'uppercase',
                                                            letterSpacing: '0.1em',
                                                            borderRadius: '4px',
                                                            border: '1px solid #D5C4AA',
                                                            backgroundColor: '#F7F2E8',
                                                            color: '#5A4A3B',
                                                            cursor: 'pointer'
                                                        }}
                                                    >
                                                        {isExpanded ? 'Hide Diff' : 'View Diff'}
                                                    </button>
                                                    {isExpanded && (
                                                        <pre style={{
                                                            margin: '0 0 10px 0',
                                                            background: '#111827',
                                                            color: '#E5E7EB',
                                                            borderRadius: '4px',
                                                            padding: '12px',
                                                            fontSize: '11px',
                                                            lineHeight: '1.5',
                                                            overflowX: 'auto',
                                                            whiteSpace: 'pre'
                                                        }}>
                                                            {item?.change || ''}
                                                        </pre>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    <div style={{ marginTop: '32px' }}>
                        <button
                            onClick={handleContinue}
                            className="clause-cta-button"
                        >
                            {config.continueLabel}
                        </button>
                    </div>
                </div>

                {toast && (
                    <div style={{
                        position: 'fixed',
                        bottom: '24px',
                        right: '24px',
                        background: '#1C1C1C',
                        color: 'white',
                        padding: '12px 16px',
                        borderRadius: '4px',
                        fontSize: '12px',
                        boxShadow: '0 6px 18px rgba(0,0,0,0.2)'
                    }}>
                        {toast}
                    </div>
                )}
            </div>
        </PageShell>
    );
}

export default FixesPage;
