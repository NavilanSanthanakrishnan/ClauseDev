import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAPIHealth } from '../hooks/useAPIHealth';
import { apiService } from '../services/api';
import { getCurrentUser, getUserFilesBucket, uploadUserFile } from '../lib/supabaseClient';
import { getFileType, formatFileSize, calculateWordCount } from '../utils/fileProcessing';
import { updateWorkflow } from '../utils/workflowStorage';
import { setRequestTracking } from '../utils/requestTracking';
import PageShell from '../components/layout/PageShell';
import SectionCard from '../components/layout/SectionCard';
import ActionBar from '../components/layout/ActionBar';
import StatusBadge from '../components/layout/StatusBadge';
import { STEP_PATHS } from '../workflow/definitions';
import { useWorkflowState } from '../hooks/useWorkflowState';

const STATE = {
    IDLE: 'idle',
    EXTRACTING: 'extracting',
    ERROR: 'error'
};

const LAST_EXTRACTION_KEY = 'clauseai.last_extraction.v1';

const sanitizeFileName = (name) => String(name || 'file').replace(/[^a-zA-Z0-9._-]/g, '_');

function UploadPage() {
    const navigate = useNavigate();
    const { isHealthy } = useAPIHealth();
    const { workflow } = useWorkflowState();
    const fileInputRef = useRef(null);
    const extractionStatus = workflow.requestTracking?.extraction?.status;

    const [currentState, setCurrentState] = useState(STATE.IDLE);
    const [selectedFile, setSelectedFile] = useState(null);
    const [error, setError] = useState(null);

    useEffect(() => {
        updateWorkflow({ currentStep: STEP_PATHS.EXTRACTION_INPUT });
    }, []);

    useEffect(() => {
        if (!workflow.extraction?.fileName) return;
        setSelectedFile((current) => {
            if (current?.name === workflow.extraction.fileName && current?.size === workflow.extraction.fileSize) {
                return current;
            }
            return {
                name: workflow.extraction.fileName,
                size: workflow.extraction.fileSize
            };
        });
    }, [workflow.extraction?.fileName, workflow.extraction?.fileSize]);

    const handleFileChange = (e) => {
        const file = e.target.files[0];
        if (file) {
            if (file.size > 10 * 1024 * 1024) {
                setError('File size must be less than 10MB');
                setCurrentState(STATE.ERROR);
                return;
            }

            const fileType = getFileType(file);
            if (!fileType) {
                setError('Unsupported file type. Please upload PDF, DOCX, or TXT files only.');
                setCurrentState(STATE.ERROR);
                return;
            }

            setSelectedFile(file);
            setError(null);
            setCurrentState(STATE.IDLE);
        }
    };

    const handleExtract = async () => {
        if (!selectedFile) {
            setError('Please upload a document first');
            setCurrentState(STATE.ERROR);
            return;
        }

        if (!isHealthy) {
            setError('Backend API is not running. Please start the server.');
            setCurrentState(STATE.ERROR);
            return;
        }

        setCurrentState(STATE.EXTRACTING);
        setError(null);

        let requestId = null;
        try {
            const user = await getCurrentUser();
            if (!user?.id) {
                throw new Error('Authentication required. Please sign in again.');
            }

            const fileType = getFileType(selectedFile);
            const bucket = getUserFilesBucket();
            const storagePath = `${user.id}/${Date.now()}_${sanitizeFileName(selectedFile.name)}`;
            await uploadUserFile(selectedFile, storagePath, bucket);

            requestId = apiService.generateRequestId();
            setRequestTracking('extraction', requestId, 'running');

            const response = await apiService.extractBillText({
                file_type: fileType,
                storage_path: storagePath,
                bucket,
                original_file_name: selectedFile.name,
                mime_type: selectedFile.type || null,
                size_bytes: selectedFile.size
            }, undefined, requestId);

            if (response.success) {
                const text = typeof response.data === 'string'
                    ? response.data
                    : (
                        response?.data?.bill_text ||
                        response?.data?.text ||
                        ''
                    );
                const hasExtractedText = typeof text === 'string' && text.trim().length > 0;

                if (!hasExtractedText) {
                    setError('No bill text could be extracted from this file. Please try another file or format.');
                    setRequestTracking('extraction', requestId, 'failed');
                    setCurrentState(STATE.ERROR);
                    return;
                }

                const stats = {
                    processingTime: response.processing_time,
                    characterCount: text.length,
                    wordCount: calculateWordCount(text),
                    fileName: selectedFile.name,
                    fileSize: formatFileSize(selectedFile.size)
                };
                const extractionPayload = {
                    text,
                    stats,
                    fileName: selectedFile.name,
                    fileSize: selectedFile.size,
                    fileType: fileType || ''
                };

                updateWorkflow({
                    currentStep: STEP_PATHS.EXTRACTION_OUTPUT,
                    billText: text,
                    extraction: {
                        originalText: text,
                        editedText: text,
                        stats,
                        fileName: selectedFile.name,
                        fileSize: selectedFile.size,
                        fileType: fileType || ''
                    }
                });
                setRequestTracking('extraction', requestId, 'completed');

                try {
                    window.localStorage.setItem(LAST_EXTRACTION_KEY, JSON.stringify(extractionPayload));
                } catch {
                    // Best effort cache for recovery when workflow sync is unavailable.
                }

                navigate(STEP_PATHS.EXTRACTION_OUTPUT, {
                    state: {
                        extraction: extractionPayload
                    }
                });
            } else {
                setError(response.data || 'Failed to extract text');
                setRequestTracking('extraction', requestId, 'failed');
                setCurrentState(STATE.ERROR);
            }
        } catch (err) {
            setError(err.message || 'Failed to extract text from file');
            setRequestTracking('extraction', null, 'failed');
            setCurrentState(STATE.ERROR);
        }
    };

    const handleTryAgain = () => {
        setError(null);
        setCurrentState(STATE.IDLE);
    };

    const statusTone = currentState === STATE.EXTRACTING ? 'running' : currentState === STATE.ERROR ? 'failed' : 'idle';

    return (
        <PageShell
            title="Bill Extraction"
            subtitle="Upload your bill and extract editable text for analysis."
            contentMaxWidth="860px"
        >
            <SectionCard
                title="Upload Bill Draft"
                subtitle="PDF, DOCX, or TXT up to 10MB"
                actions={<StatusBadge value={statusTone} />}
            >
                <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                    {extractionStatus && (
                        <div style={{ fontSize: '12px', color: '#8B7355' }}>
                            Status: {extractionStatus}
                        </div>
                    )}

                    {error && (
                        <div style={{
                            backgroundColor: '#FEF2F2',
                            border: '1px solid #F5C3BE',
                            borderRadius: '8px',
                            padding: '12px 14px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '10px'
                        }}>
                            <div style={{ fontSize: '12px', color: '#6B5444' }}>{error}</div>
                            <button onClick={handleTryAgain} className="clause-btn clause-btn-secondary">
                                Try Again
                            </button>
                        </div>
                    )}

                    <div
                        onClick={() => fileInputRef.current?.click()}
                        className="clause-dropzone"
                        style={{
                            padding: '42px',
                            textAlign: 'center',
                            cursor: 'pointer'
                        }}
                    >
                        <svg style={{ margin: '0 auto 16px', height: '48px', width: '48px', color: '#C5A47E' }} stroke="currentColor" fill="none" viewBox="0 0 48 48">
                            <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        <p style={{ fontSize: '14px', fontWeight: 600, color: '#1C1C1C', margin: '0 0 4px 0' }}>
                            Select Document
                        </p>
                        <p style={{ fontSize: '12px', color: '#8B7355', margin: 0 }}>
                            Click to choose a file
                        </p>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".pdf,.docx,.txt"
                            onChange={handleFileChange}
                            style={{ display: 'none' }}
                        />
                    </div>

                    {selectedFile && (
                        <div style={{ fontSize: '12px', color: '#6B5444' }}>
                            Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})
                        </div>
                    )}

                    <ActionBar>
                        {currentState === STATE.EXTRACTING ? (
                            <>
                                <div className="clause-spinner" style={{
                                    width: '22px',
                                    height: '22px',
                                    border: '3px solid #EAE3D5',
                                    borderTopColor: '#C5A47E',
                                    borderRadius: '50%'
                                }} />
                                <span style={{ fontSize: '13px', color: '#6B5444' }}>Extracting bill text...</span>
                            </>
                        ) : (
                            <button
                                onClick={handleExtract}
                                disabled={!selectedFile || !isHealthy}
                                className={`clause-btn clause-btn-primary ${(!selectedFile || !isHealthy) ? 'is-disabled' : ''}`}
                            >
                                Extract Bill Text
                            </button>
                        )}
                    </ActionBar>
                </div>
            </SectionCard>
        </PageShell>
    );
}

export default UploadPage;
