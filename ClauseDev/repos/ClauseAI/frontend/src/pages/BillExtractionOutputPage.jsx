import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { updateWorkflow } from '../utils/workflowStorage';
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

function BillExtractionOutputPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const { workflow } = useWorkflowState();
    const [text, setText] = useState('');
    const [stats, setStats] = useState(null);
    const [cachedExtraction] = useState(() => readLastExtraction());
    const extractionStatus = workflow.requestTracking?.extraction?.status;
    const routeExtraction = location.state?.extraction || null;
    const extractedText = (
        workflow.extraction?.editedText ||
        workflow.extraction?.originalText ||
        routeExtraction?.text ||
        cachedExtraction?.text ||
        workflow.billText ||
        ''
    );

    useEffect(() => {
        const fallbackExtraction = routeExtraction?.text ? routeExtraction : cachedExtraction;

        if (!workflow.extraction?.editedText && fallbackExtraction?.text) {
            updateWorkflow({
                billText: fallbackExtraction.text,
                extraction: {
                    originalText: fallbackExtraction.text,
                    editedText: fallbackExtraction.text,
                    stats: fallbackExtraction.stats || null,
                    fileName: fallbackExtraction.fileName || '',
                    fileSize: fallbackExtraction.fileSize || 0,
                    fileType: fallbackExtraction.fileType || ''
                }
            });
        }

        if (workflow.currentStep !== STEP_PATHS.EXTRACTION_OUTPUT) {
            updateWorkflow({ currentStep: STEP_PATHS.EXTRACTION_OUTPUT });
        }
        setText(extractedText);
        setStats(workflow.extraction.stats || routeExtraction?.stats || cachedExtraction?.stats || null);
    }, [
        workflow.currentStep,
        workflow.extraction?.editedText,
        workflow.extraction?.originalText,
        workflow.extraction?.stats,
        workflow.billText,
        extractedText,
        routeExtraction,
        cachedExtraction
    ]);

    const handleChange = (value) => {
        setText(value);
        updateWorkflow({
            billText: value,
            extraction: { editedText: value }
        });
    };

    const handleContinue = () => {
        const persistedText = (text || '').trim().length > 0 ? text : extractedText;
        const nextPatch = {
            currentStep: STEP_PATHS.METADATA
        };

        if (persistedText) {
            nextPatch.billText = persistedText;
            nextPatch.extraction = {
                originalText: workflow.extraction?.originalText || persistedText,
                editedText: persistedText,
                stats: stats || workflow.extraction?.stats || null,
                fileName: workflow.extraction?.fileName || routeExtraction?.fileName || cachedExtraction?.fileName || '',
                fileSize: workflow.extraction?.fileSize || routeExtraction?.fileSize || cachedExtraction?.fileSize || 0,
                fileType: workflow.extraction?.fileType || routeExtraction?.fileType || cachedExtraction?.fileType || ''
            };
        }

        updateWorkflow(nextPatch);
        navigate(STEP_PATHS.METADATA);
    };

    return (
        <PageShell>
            <div style={{ padding: '8px 0' }}>
                <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
                    {!extractedText && (
                        <div style={{
                            background: '#FDFCF8',
                            border: '1px solid #EAE3D5',
                            borderRadius: '4px',
                            padding: '36px',
                            marginBottom: '24px'
                        }}>
                            <h2 style={{
                                fontFamily: "'Crimson Pro', serif",
                                fontSize: '32px',
                                fontWeight: 600,
                                color: '#1C1C1C',
                                margin: '0 0 10px 0'
                            }}>
                                No extracted text available
                            </h2>
                            <p style={{ fontSize: '14px', color: '#6B5444', margin: '0 0 18px 0' }}>
                                {extractionStatus === 'running'
                                    ? 'Extraction is still running. Please wait a moment.'
                                    : 'Please go back and extract bill text again.'}
                            </p>
                            <button
                                onClick={() => navigate(STEP_PATHS.EXTRACTION_INPUT)}
                                className="clause-btn clause-btn-primary"
                            >
                                Back to Upload
                            </button>
                        </div>
                    )}

                    {extractedText && (
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
                            Extracted Bill Text
                        </h1>
                        <p style={{ fontSize: '16px', color: '#6B5444', marginBottom: '24px' }}>
                            Review and edit the extracted text before moving forward.
                        </p>

                        {stats && (
                            <div style={{
                                display: 'flex',
                                gap: '16px',
                                flexWrap: 'wrap',
                                marginBottom: '24px'
                            }}>
                                {[
                                    { label: 'Characters', value: stats.characterCount?.toLocaleString?.() || stats.characterCount },
                                    { label: 'Words', value: stats.wordCount?.toLocaleString?.() || stats.wordCount },
                                    { label: 'Processing', value: stats.processingTime ? `${stats.processingTime.toFixed(2)}s` : null },
                                    { label: 'File', value: stats.fileName }
                                ].filter(item => item.value).map((item) => (
                                    <div key={item.label} style={{
                                        background: '#FAF9F7',
                                        border: '1px solid #EAE3D5',
                                        borderRadius: '4px',
                                        padding: '12px 16px'
                                    }}>
                                        <div style={{
                                            fontSize: '10px',
                                            fontWeight: 'bold',
                                            letterSpacing: '0.2em',
                                            textTransform: 'uppercase',
                                            color: '#8B7355',
                                            marginBottom: '4px'
                                        }}>
                                            {item.label}
                                        </div>
                                        <div style={{ fontSize: '16px', fontWeight: 600, color: '#1C1C1C' }}>{item.value}</div>
                                    </div>
                                ))}
                            </div>
                        )}

                        <div style={{
                            background: 'white',
                            border: '1px solid #EAE3D5',
                            borderRadius: '4px',
                            padding: '20px'
                        }}>
                            <div style={{
                                fontSize: '10px',
                                fontWeight: 'bold',
                                letterSpacing: '0.3em',
                                textTransform: 'uppercase',
                                color: '#8B7355',
                                marginBottom: '12px'
                            }}>
                                Editable Bill Text
                            </div>
                            <textarea
                                value={text}
                                onChange={(e) => handleChange(e.target.value)}
                                style={{
                                    width: '100%',
                                    minHeight: '420px',
                                    border: '1px solid #EAE3D5',
                                    borderRadius: '4px',
                                    padding: '16px',
                                    fontFamily: 'monospace',
                                    fontSize: '13px',
                                    lineHeight: '1.7',
                                    color: '#1C1C1C',
                                    resize: 'vertical',
                                    overflowY: 'auto'
                                }}
                            />
                        </div>

                        <div style={{ marginTop: '32px' }}>
                            <button
                                onClick={handleContinue}
                                className="clause-cta-button"
                            >
                                Proceed to Metadata
                            </button>
                        </div>
                        </div>
                    )}
                </div>
            </div>
        </PageShell>
    );
}

export default BillExtractionOutputPage;
