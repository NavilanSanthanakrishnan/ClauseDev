import { apiService } from '../services/api';
import { normalizeFixClassificationPayload } from '../utils/fixMapping';
import { sanitizeAnalysisForDisplay } from '../utils/analysisFormatting';
import { extractOptimizations } from '../utils/fixChangeApplicator';
import { STEP_PATHS } from './definitions';

const buildBillAnalysisInputs = (workflow) => {
    const billsData = workflow.similarBillsLoaded?.data || {};
    const passedBills = billsData.Passed_Bills || [];
    const failedBills = billsData.Failed_Bills || [];

    const userBill = billsData.User_Bill || {
        title: workflow.metadata.title,
        description: workflow.metadata.description,
        summary: workflow.metadata.summary,
        categorized_sentences: workflow.metadata.categorized_sentences || {}
    };

    const policyArea = workflow.metadata.summary || workflow.metadata.description;

    return {
        userBill,
        userBillRawText: workflow.billText,
        passedBills,
        failedBills,
        policyArea,
        jurisdiction: 'CA'
    };
};

const parseBillSavedState = (workflow) => {
    if (!workflow.billAnalysis?.report) return null;
    const savedClassification = normalizeFixClassificationPayload(
        workflow.billAnalysis,
        workflow.billAnalysis?.directImprovements || []
    );
    return {
        reportText: workflow.billAnalysis.report,
        structuredData: null,
        generatedFixes: savedClassification.validImprovements,
        context: {
            reportText: workflow.billAnalysis.report,
            structuredData: null
        }
    };
};

const parseLegalSavedState = (workflow) => {
    if (!workflow.legalAnalysis?.structuredData) return null;
    const savedStructured = workflow.legalAnalysis.structuredData;
    const savedFixes = normalizeFixClassificationPayload(
        workflow.legalAnalysis,
        savedStructured?.legal_improvements || []
    ).validImprovements;
    return {
        reportText: workflow.legalAnalysis.report || '',
        structuredData: savedStructured,
        generatedFixes: savedFixes,
        context: {
            reportText: workflow.legalAnalysis.report || '',
            structuredData: savedStructured
        }
    };
};

const parseStakeholderSavedState = (workflow) => {
    if (!workflow.stakeholderAnalysis?.structuredData) return null;
    const savedStructured = workflow.stakeholderAnalysis.structuredData;
    const savedFixes = normalizeFixClassificationPayload(
        workflow.stakeholderAnalysis,
        extractOptimizations(savedStructured)
    ).validImprovements;
    return {
        reportText: workflow.stakeholderAnalysis.report || '',
        structuredData: savedStructured,
        generatedFixes: savedFixes,
        context: {
            reportText: workflow.stakeholderAnalysis.report || '',
            structuredData: savedStructured
        }
    };
};

export const ANALYSIS_CONFIG = {
    bill: {
        key: 'bill',
        title: 'Bill Analysis Report',
        subtitle: 'Review the report, then generate fixes in a separate step.',
        currentStep: STEP_PATHS.BILL_ANALYSIS_REPORT,
        prerequisiteRoute: STEP_PATHS.SIMILAR_BILLS_LOADER,
        isPrerequisiteMet: (workflow) => Boolean(workflow.similarBillsLoaded?.data),
        trackingKey: 'billAnalysis',
        continueRoute: STEP_PATHS.BILL_ANALYSIS_FIXES,
        applyFixesLabel: 'Apply Fixes',
        generateFixesLabel: 'Generate Fixes',
        toolCallTitle: null,
        showToolHistory: false,
        initialReportOperation: 'Generating bill report...',
        initialFixesOperation: 'Generating fixes...',
        contentMaxWidth: '1000px',
        parseSavedState: parseBillSavedState,
        startReport: async (workflow, requestId) => {
            const inputs = buildBillAnalysisInputs(workflow);
            return apiService.analyzeBill(
                inputs.userBill,
                inputs.userBillRawText,
                inputs.passedBills,
                inputs.failedBills,
                inputs.policyArea,
                inputs.jurisdiction,
                requestId,
                { phase: 'report' }
            );
        },
        getReportStatus: (requestId) => apiService.getBillAnalysisStatus(requestId, 'report'),
        getReportResult: (requestId) => apiService.getBillAnalysisResult(requestId, 'report'),
        parseReportPartial: (status) => ({
            reportText: status?.partial_data?.report || status?.data?.report || '',
            toolHistory: [],
            currentToolCall: null
        }),
        parseReportResult: (workflow, finalData) => {
            const reportText = finalData?.report || '';
            const existingClassification = normalizeFixClassificationPayload(
                workflow.billAnalysis,
                workflow.billAnalysis?.directImprovements || []
            );
            return {
                reportText,
                structuredData: null,
                generatedFixes: existingClassification.validImprovements,
                workflowPatch: {
                    billAnalysis: {
                        report: reportText,
                        improvements: existingClassification.improvements,
                        directImprovements: existingClassification.validImprovements,
                        validImprovementIndices: existingClassification.validImprovementIndices,
                        invalidImprovements: existingClassification.invalidImprovements,
                        validationSummary: existingClassification.validationSummary,
                        warning: existingClassification.warning,
                        processingTime: workflow.billAnalysis?.processingTime || null
                    }
                }
            };
        },
        startFixes: async (workflow, requestId, context) => {
            const inputs = buildBillAnalysisInputs(workflow);
            return apiService.analyzeBill(
                inputs.userBill,
                inputs.userBillRawText,
                inputs.passedBills,
                inputs.failedBills,
                inputs.policyArea,
                inputs.jurisdiction,
                requestId,
                {
                    phase: 'fixes',
                    reportContext: {
                        report: context?.reportText || ''
                    }
                }
            );
        },
        getFixesStatus: (requestId) => apiService.getBillAnalysisStatus(requestId, 'fixes'),
        getFixesResult: (requestId) => apiService.getBillAnalysisResult(requestId, 'fixes'),
        parseFixesPartial: (status) => normalizeFixClassificationPayload(status?.partial_data).validImprovements,
        parseFixesResult: (workflow, finalData, context) => {
            const classifiedFixes = normalizeFixClassificationPayload(finalData);
            const nextFixes = classifiedFixes.validImprovements;
            return {
                generatedFixes: nextFixes,
                workflowPatch: {
                    billAnalysis: {
                        ...workflow.billAnalysis,
                        improvements: classifiedFixes.improvements,
                        validImprovementIndices: classifiedFixes.validImprovementIndices,
                        invalidImprovements: classifiedFixes.invalidImprovements,
                        validationSummary: classifiedFixes.validationSummary,
                        warning: classifiedFixes.warning,
                        report: context?.reportText || workflow.billAnalysis?.report || '',
                        directImprovements: nextFixes
                    }
                }
            };
        }
    },
    legal: {
        key: 'legal',
        title: 'Legal Conflict Report',
        subtitle: 'Research first, then generate legal fixes in a second call.',
        currentStep: STEP_PATHS.LEGAL_ANALYSIS_REPORT,
        prerequisiteRoute: STEP_PATHS.BILL_ANALYSIS_REPORT,
        isPrerequisiteMet: (workflow) => Boolean(workflow.billAnalysis?.report),
        trackingKey: 'conflictAnalysis',
        continueRoute: STEP_PATHS.LEGAL_ANALYSIS_FIXES,
        applyFixesLabel: 'Apply Legal Fixes',
        generateFixesLabel: 'Generate Legal Fixes',
        toolCallTitle: 'Legal Tool Calls',
        showToolHistory: true,
        initialReportOperation: 'Generating legal report...',
        initialFixesOperation: 'Generating legal fixes...',
        contentMaxWidth: '1200px',
        parseSavedState: parseLegalSavedState,
        startReport: (workflow, requestId) => apiService.analyzeConflicts(workflow.billText, requestId, { phase: 'report' }),
        getReportStatus: (requestId) => apiService.getConflictAnalysisStatus(requestId, 'report'),
        getReportResult: (requestId) => apiService.getConflictAnalysisResult(requestId, 'report'),
        parseReportPartial: (status) => {
            const partialStructured = status?.partial_data?.structured_data || status?.partial_data?.structuredData;
            return {
                reportText: sanitizeAnalysisForDisplay(status?.partial_data?.analysis, partialStructured, 'Legal Conflict Summary'),
                toolHistory: Array.isArray(status?.tool_calls_history) ? status.tool_calls_history : [],
                currentToolCall: status?.current_tool_call || null
            };
        },
        parseReportResult: (workflow, finalData) => {
            const data = finalData?.structured_data || finalData;
            const normalizedData = {
                ...data,
                legal_improvements: []
            };
            const renderedAnalysis = sanitizeAnalysisForDisplay(finalData?.analysis, normalizedData, 'Legal Conflict Summary');
            return {
                reportText: renderedAnalysis,
                structuredData: normalizedData,
                generatedFixes: [],
                workflowPatch: {
                    legalAnalysis: {
                        structuredData: normalizedData,
                        report: renderedAnalysis,
                        improvements: Array.isArray(workflow.legalAnalysis?.improvements) ? workflow.legalAnalysis.improvements : [],
                        validImprovementIndices: Array.isArray(workflow.legalAnalysis?.validImprovementIndices)
                            ? workflow.legalAnalysis.validImprovementIndices
                            : [],
                        invalidImprovements: Array.isArray(workflow.legalAnalysis?.invalidImprovements)
                            ? workflow.legalAnalysis.invalidImprovements
                            : [],
                        validationSummary: workflow.legalAnalysis?.validationSummary || null,
                        warning: workflow.legalAnalysis?.warning || null
                    }
                }
            };
        },
        startFixes: (workflow, requestId, context) => apiService.analyzeConflicts(workflow.billText, requestId, {
            phase: 'fixes',
            reportContext: {
                analysis: context?.reportText || '',
                structured_data: context?.structuredData || null
            }
        }),
        getFixesStatus: (requestId) => apiService.getConflictAnalysisStatus(requestId, 'fixes'),
        getFixesResult: (requestId) => apiService.getConflictAnalysisResult(requestId, 'fixes'),
        parseFixesPartial: (status) => normalizeFixClassificationPayload(status?.partial_data).validImprovements,
        parseFixesResult: (workflow, finalData, context) => {
            const classifiedFixes = normalizeFixClassificationPayload(finalData);
            return {
                generatedFixes: classifiedFixes.validImprovements,
                workflowPatch: {
                    legalAnalysis: {
                        ...workflow.legalAnalysis,
                        structuredData: workflow.legalAnalysis?.structuredData || context?.structuredData || null,
                        improvements: classifiedFixes.improvements,
                        validImprovementIndices: classifiedFixes.validImprovementIndices,
                        invalidImprovements: classifiedFixes.invalidImprovements,
                        validationSummary: classifiedFixes.validationSummary,
                        warning: classifiedFixes.warning,
                        report: workflow.legalAnalysis?.report || context?.reportText || ''
                    }
                }
            };
        }
    },
    stakeholder: {
        key: 'stakeholder',
        title: 'Stakeholder Analysis Report',
        subtitle: 'Research first, then generate stakeholder fixes in a second call.',
        currentStep: STEP_PATHS.STAKEHOLDER_REPORT,
        prerequisiteRoute: STEP_PATHS.LEGAL_ANALYSIS_REPORT,
        isPrerequisiteMet: (workflow) => Boolean(workflow.legalAnalysis?.structuredData),
        trackingKey: 'stakeholderAnalysis',
        continueRoute: STEP_PATHS.STAKEHOLDER_FIXES,
        applyFixesLabel: 'Apply Stakeholder Fixes',
        generateFixesLabel: 'Generate Stakeholder Fixes',
        toolCallTitle: 'Stakeholder Tool Calls',
        showToolHistory: true,
        initialReportOperation: 'Generating stakeholder report...',
        initialFixesOperation: 'Generating stakeholder fixes...',
        contentMaxWidth: '1200px',
        parseSavedState: parseStakeholderSavedState,
        startReport: (workflow, requestId) => apiService.analyzeStakeholders(workflow.billText, requestId, { phase: 'report' }),
        getReportStatus: (requestId) => apiService.getStakeholderAnalysisStatus(requestId, 'report'),
        getReportResult: (requestId) => apiService.getStakeholderAnalysisResult(requestId, 'report'),
        parseReportPartial: (status) => {
            const partialStructured = status?.partial_data?.structured_data || status?.partial_data?.structuredData;
            return {
                reportText: sanitizeAnalysisForDisplay(status?.partial_data?.analysis, partialStructured, 'Stakeholder Analysis Summary'),
                toolHistory: Array.isArray(status?.tool_calls_history) ? status.tool_calls_history : [],
                currentToolCall: status?.current_tool_call || null
            };
        },
        parseReportResult: (workflow, finalData) => {
            const data = finalData?.structured_data || finalData;
            const normalizedData = {
                ...data,
                language_optimizations: []
            };
            const renderedAnalysis = sanitizeAnalysisForDisplay(finalData?.analysis, normalizedData, 'Stakeholder Analysis Summary');
            return {
                reportText: renderedAnalysis,
                structuredData: normalizedData,
                generatedFixes: [],
                workflowPatch: {
                    stakeholderAnalysis: {
                        structuredData: normalizedData,
                        report: renderedAnalysis,
                        improvements: Array.isArray(workflow.stakeholderAnalysis?.improvements) ? workflow.stakeholderAnalysis.improvements : [],
                        validImprovementIndices: Array.isArray(workflow.stakeholderAnalysis?.validImprovementIndices)
                            ? workflow.stakeholderAnalysis.validImprovementIndices
                            : [],
                        invalidImprovements: Array.isArray(workflow.stakeholderAnalysis?.invalidImprovements)
                            ? workflow.stakeholderAnalysis.invalidImprovements
                            : [],
                        validationSummary: workflow.stakeholderAnalysis?.validationSummary || null,
                        warning: workflow.stakeholderAnalysis?.warning || null
                    }
                }
            };
        },
        startFixes: (workflow, requestId, context) => apiService.analyzeStakeholders(workflow.billText, requestId, {
            phase: 'fixes',
            reportContext: {
                analysis: context?.reportText || '',
                structured_data: context?.structuredData || null
            }
        }),
        getFixesStatus: (requestId) => apiService.getStakeholderAnalysisStatus(requestId, 'fixes'),
        getFixesResult: (requestId) => apiService.getStakeholderAnalysisResult(requestId, 'fixes'),
        parseFixesPartial: (status) => normalizeFixClassificationPayload(status?.partial_data).validImprovements,
        parseFixesResult: (workflow, finalData, context) => {
            const classifiedFixes = normalizeFixClassificationPayload(finalData);
            return {
                generatedFixes: classifiedFixes.validImprovements,
                workflowPatch: {
                    stakeholderAnalysis: {
                        ...workflow.stakeholderAnalysis,
                        structuredData: workflow.stakeholderAnalysis?.structuredData || context?.structuredData || null,
                        improvements: classifiedFixes.improvements,
                        validImprovementIndices: classifiedFixes.validImprovementIndices,
                        invalidImprovements: classifiedFixes.invalidImprovements,
                        validationSummary: classifiedFixes.validationSummary,
                        warning: classifiedFixes.warning,
                        report: workflow.stakeholderAnalysis?.report || context?.reportText || ''
                    }
                }
            };
        }
    }
};
