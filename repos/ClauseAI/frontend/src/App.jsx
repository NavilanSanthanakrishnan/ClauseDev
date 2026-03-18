import React, { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { consumeAuthCallback } from './lib/supabaseClient';
import { getWorkflow, hydrateWorkflowFromServer, updateWorkflow } from './utils/workflowStorage';
import { useWorkflowState } from './hooks/useWorkflowState';
import { STEP_PATHS, normalizeStepPath } from './workflow/definitions';
import AppErrorBoundary from './components/app/AppErrorBoundary';

const HomePage = lazy(() => import('./pages/HomePage'));
const ApiCheckPage = lazy(() => import('./pages/ApiCheckPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const UploadPage = lazy(() => import('./pages/UploadPage'));
const BillExtractionOutputPage = lazy(() => import('./pages/BillExtractionOutputPage'));
const MetadataPage = lazy(() => import('./pages/MetadataPage'));
const SimilarBillsPage = lazy(() => import('./pages/SimilarBillsPage'));
const SimilarBillsLoaderPage = lazy(() => import('./pages/SimilarBillsLoaderPage'));
const BillAnalysisPage = lazy(() => import('./pages/BillAnalysisPage'));
const BillAnalysisFixesPage = lazy(() => import('./pages/BillAnalysisFixesPage'));
const ConflictAnalysisPage = lazy(() => import('./pages/ConflictAnalysisPage'));
const LegalAnalysisFixesPage = lazy(() => import('./pages/LegalAnalysisFixesPage'));
const StakeholderAnalysisPage = lazy(() => import('./pages/StakeholderAnalysisPage'));
const StakeholderAnalysisFixesPage = lazy(() => import('./pages/StakeholderAnalysisFixesPage'));
const FinalReportPage = lazy(() => import('./pages/FinalReportPage'));
const FinalEditingPage = lazy(() => import('./pages/FinalEditingPage'));
const BillInspectPage = lazy(() => import('./pages/BillInspectPage'));

function WorkflowRedirector() {
    const navigate = useNavigate();
    const location = useLocation();
    
    useEffect(() => {
        const workflow = getWorkflow();
        if (location.pathname === STEP_PATHS.HOME && workflow.currentStep && workflow.currentStep !== STEP_PATHS.HOME) {
            const normalized = normalizeStepPath(workflow.currentStep);
            if (normalized !== workflow.currentStep) {
                updateWorkflow({ currentStep: normalized });
            }
            navigate(normalized, { replace: true });
        }
    }, [location.pathname, navigate]);
    
    return null;
}

function AppRoutes() {
    const location = useLocation();
    const { hydrated } = useWorkflowState();
    
    useEffect(() => {
        consumeAuthCallback();
        hydrateWorkflowFromServer();
    }, []);

    if (!hydrated) {
        return (
            <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: '24px', color: '#6B5444' }}>
                Restoring workflow...
            </div>
        );
    }
    
    return (
        <AppErrorBoundary>
            <WorkflowRedirector />
            <Suspense fallback={<div style={{ padding: '24px', color: '#6B5444' }}>Loading...</div>}>
                <Routes location={location}>
                    <Route path={STEP_PATHS.HOME} element={<HomePage />} />
                    <Route path={STEP_PATHS.LOGIN} element={<LoginPage />} />
                    <Route path={STEP_PATHS.API_CHECK} element={<ApiCheckPage />} />
                    <Route path={STEP_PATHS.EXTRACTION_INPUT} element={<UploadPage />} />
                    <Route path={STEP_PATHS.EXTRACTION_OUTPUT} element={<BillExtractionOutputPage />} />
                    <Route path={STEP_PATHS.DOCUMENT} element={<Navigate to={STEP_PATHS.EXTRACTION_OUTPUT} replace />} />
                    <Route path={STEP_PATHS.METADATA} element={<MetadataPage />} />
                    <Route path={STEP_PATHS.SIMILAR_BILLS} element={<SimilarBillsPage />} />
                    <Route path={STEP_PATHS.SIMILAR_BILLS_LOADER} element={<SimilarBillsLoaderPage />} />
                    <Route path={STEP_PATHS.BILL_ANALYSIS_REPORT} element={<BillAnalysisPage />} />
                    <Route path={STEP_PATHS.BILL_ANALYSIS_FIXES} element={<BillAnalysisFixesPage />} />
                    <Route path={STEP_PATHS.LEGAL_ANALYSIS_REPORT} element={<ConflictAnalysisPage />} />
                    <Route path={STEP_PATHS.LEGAL_ANALYSIS_FIXES} element={<LegalAnalysisFixesPage />} />
                    <Route path={STEP_PATHS.STAKEHOLDER_REPORT} element={<StakeholderAnalysisPage />} />
                    <Route path={STEP_PATHS.STAKEHOLDER_FIXES} element={<StakeholderAnalysisFixesPage />} />
                    <Route path={STEP_PATHS.BILL_INSPECT} element={<BillInspectPage />} />
                    <Route path={STEP_PATHS.FINAL_REPORT} element={<FinalReportPage />} />
                    <Route path={STEP_PATHS.FINAL_EDITING} element={<FinalEditingPage />} />
                </Routes>
            </Suspense>
        </AppErrorBoundary>
    );
}

function App() {
    return (
        <Router>
        <AppRoutes />
        </Router>
    );
}

export default App;
