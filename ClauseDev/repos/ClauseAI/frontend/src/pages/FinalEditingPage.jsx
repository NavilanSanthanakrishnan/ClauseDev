import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Document, Packer, Paragraph } from 'docx';
import { updateWorkflow } from '../utils/workflowStorage';
import PageShell from '../components/layout/PageShell';
import SectionCard from '../components/layout/SectionCard';
import ActionBar from '../components/layout/ActionBar';
import { STEP_PATHS } from '../workflow/definitions';
import { useWorkflowState } from '../hooks/useWorkflowState';

function FinalEditingPage() {
    const navigate = useNavigate();
    const { workflow } = useWorkflowState();
    const [text, setText] = useState('');

    useEffect(() => {
        if (!workflow.billText) {
            navigate(STEP_PATHS.FINAL_REPORT);
            return;
        }
        if (workflow.currentStep !== STEP_PATHS.FINAL_EDITING) {
            updateWorkflow({ currentStep: STEP_PATHS.FINAL_EDITING });
        }
        setText((current) => (current === (workflow.billText || '') ? current : (workflow.billText || '')));
    }, [navigate, workflow.billText, workflow.currentStep]);

    const handleChange = (value) => {
        setText(value);
        updateWorkflow({ billText: value });
    };

    const handleDownload = async () => {
        const paragraphs = (text || '').split('\n').map((line) => new Paragraph(line));
        const doc = new Document({
            sections: [{ children: paragraphs }]
        });

        const blob = await Packer.toBlob(doc);
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'final-bill.docx';
        link.click();
        URL.revokeObjectURL(url);
    };

    return (
        <PageShell
            title="Final Editing"
            subtitle="Review the complete bill text and export the final draft as DOCX."
            contentMaxWidth="1100px"
        >
            <SectionCard title="Bill Text">
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <textarea
                        value={text}
                        onChange={(e) => handleChange(e.target.value)}
                        style={{
                            width: '100%',
                            minHeight: '520px',
                            border: '1px solid #EAE3D5',
                            borderRadius: '8px',
                            padding: '16px',
                            fontFamily: 'monospace',
                            fontSize: '13px',
                            lineHeight: '1.7',
                            color: '#1C1C1C',
                            resize: 'vertical',
                            overflowY: 'auto'
                        }}
                    />
                    <ActionBar>
                        <button onClick={handleDownload} className="clause-btn clause-btn-primary">
                            Download DOCX
                        </button>
                    </ActionBar>
                </div>
            </SectionCard>
        </PageShell>
    );
}

export default FinalEditingPage;
