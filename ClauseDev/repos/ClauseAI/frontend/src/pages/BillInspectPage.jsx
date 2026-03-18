import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { apiService } from '../services/api';
import { getWorkflow } from '../utils/workflowStorage';
import PageShell from '../components/layout/PageShell';
import SectionCard from '../components/layout/SectionCard';
import ActionBar from '../components/layout/ActionBar';

function BillInspectPage() {
    const navigate = useNavigate();
    const location = useLocation();
    const [searchParams] = useSearchParams();

    const billId = searchParams.get('billId') || '';
    const source = searchParams.get('source') || 'similar';
    const incomingState = useMemo(() => location.state || {}, [location.state]);

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [inspectData, setInspectData] = useState(null);

    useEffect(() => {
        const runInspection = async () => {
            setLoading(true);
            setError('');

            try {
                const workflow = getWorkflow();
                const userText = incomingState.billText || workflow.billText || workflow.extraction?.editedText || '';
                const payload = {
                    bill_id: billId || undefined,
                    bill_text: billId ? undefined : userText,
                    jurisdiction: 'CA',
                    source,
                    title: incomingState.title,
                    description: incomingState.description
                };
                const response = await apiService.inspectBill(payload);
                if (!response.success || !response.data?.cleaned_text) {
                    throw new Error(response.data?.Error || 'Inspection failed');
                }
                setInspectData(response.data);
            } catch (err) {
                setError(err.message || 'Failed to inspect bill text');
            } finally {
                setLoading(false);
            }
        };

        runInspection();
    }, [billId, incomingState.billText, incomingState.description, incomingState.title, source]);

    const title = inspectData?.title || inspectData?.bill_number || incomingState.title || (billId ? `Bill ${billId}` : 'User Bill');
    const description = inspectData?.description || incomingState.description || 'Full bill text inspection view.';

    return (
        <PageShell
            title={title}
            subtitle={description}
            contentMaxWidth="1100px"
        >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <SectionCard title="Inspection">
                    <ActionBar>
                        <button className="clause-btn clause-btn-secondary" onClick={() => navigate(-1)}>
                            Back
                        </button>
                        {inspectData?.bill_number && (
                            <span style={{ fontSize: '12px', color: '#6B5444' }}>Bill Number: {inspectData.bill_number}</span>
                        )}
                        {inspectData?.bill_id && (
                            <span style={{ fontSize: '12px', color: '#6B5444' }}>Internal ID: {inspectData.bill_id}</span>
                        )}
                        {inspectData?.source && (
                            <span style={{ fontSize: '12px', color: '#6B5444', textTransform: 'capitalize' }}>
                                Source: {inspectData.source}
                            </span>
                        )}
                    </ActionBar>
                </SectionCard>

                {error && (
                    <SectionCard title="Error">
                        <div style={{ fontSize: '13px', color: '#B42318' }}>{error}</div>
                    </SectionCard>
                )}

                {loading && (
                    <SectionCard title="Loading">
                        <div style={{ fontSize: '13px', color: '#6B5444' }}>Preparing bill text inspection...</div>
                    </SectionCard>
                )}

                {!loading && inspectData && (
                    <>
                        <SectionCard title="Stats">
                            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '12px', color: '#6B5444' }}>
                                <span>Characters: {inspectData.char_count?.toLocaleString?.() || inspectData.char_count}</span>
                                <span>Lines: {inspectData.line_count?.toLocaleString?.() || inspectData.line_count}</span>
                                {inspectData.date_presented && <span>Presented: {inspectData.date_presented}</span>}
                                {inspectData.date_passed && <span>Passed: {inspectData.date_passed}</span>}
                            </div>
                            {inspectData.bill_url && (
                                <a
                                    href={inspectData.bill_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    style={{ display: 'inline-block', marginTop: '10px', fontSize: '12px', color: '#2563EB' }}
                                >
                                    Open official bill page
                                </a>
                            )}
                        </SectionCard>

                        <SectionCard title="Cleaned Bill Text">
                            <pre style={{
                                margin: 0,
                                whiteSpace: 'pre-wrap',
                                background: '#fff',
                                border: '1px solid #EAE3D5',
                                borderRadius: '4px',
                                padding: '16px',
                                fontFamily: "'Crimson Pro', serif",
                                fontSize: '15px',
                                lineHeight: '1.8',
                                color: '#1C1C1C',
                                maxHeight: '65vh',
                                overflowY: 'auto'
                            }}>
                                {inspectData.cleaned_text}
                            </pre>
                        </SectionCard>
                    </>
                )}
            </div>
        </PageShell>
    );
}

export default BillInspectPage;
