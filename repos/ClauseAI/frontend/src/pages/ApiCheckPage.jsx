import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAPIHealth } from '../hooks/useAPIHealth';
import { apiService } from '../services/api';
import { updateWorkflow } from '../utils/workflowStorage';
import PageShell from '../components/layout/PageShell';
import SectionCard from '../components/layout/SectionCard';
import ActionBar from '../components/layout/ActionBar';
import StatusBadge from '../components/layout/StatusBadge';
import { STEP_PATHS } from '../workflow/definitions';

function ApiCheckPage() {
    const navigate = useNavigate();
    const { isHealthy, version, isChecking } = useAPIHealth();
    const [authStatus, setAuthStatus] = React.useState('unknown');

    React.useEffect(() => {
        updateWorkflow({ currentStep: STEP_PATHS.API_CHECK });
    }, []);

    React.useEffect(() => {
        const ensureAuth = async () => {
            if (!isHealthy || isChecking) return;
            try {
                const status = await apiService.getAuthStatus();
                if (!status.enabled) {
                    setAuthStatus('disabled');
                    return;
                }
                setAuthStatus(status.authenticated ? 'ready' : 'required');
                return;
            } catch (err) {
                setAuthStatus('unknown');
                return;
            }
        };
        ensureAuth();
    }, [isHealthy, isChecking]);

    const handleContinue = () => {
        updateWorkflow({ currentStep: STEP_PATHS.EXTRACTION_INPUT });
        navigate(STEP_PATHS.EXTRACTION_INPUT);
    };

    const apiStatusLabel = isChecking ? 'loading' : isHealthy ? 'completed' : 'failed';

    return (
        <PageShell
            title="API Check"
            subtitle="ClauseAI needs the backend service online before extraction starts."
            contentMaxWidth="900px"
        >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', alignItems: 'center' }}>
                <SectionCard
                    title={isChecking ? 'Checking API Status...' : isHealthy ? 'Backend Online' : 'Backend Offline'}
                    subtitle={isHealthy ? `Connected to API ${version ? `(${version})` : ''}` : 'Start backend at http://localhost:8000 before continuing.'}
                    actions={<StatusBadge value={apiStatusLabel} />}
                    style={{ width: '100%', maxWidth: '760px' }}
                >
                    <div className="clause-centered-stack">
                        {isHealthy && authStatus !== 'unknown' && (
                            <div style={{ fontSize: '13px', color: '#6B5444' }}>
                                Auth: {authStatus === 'ready' ? 'Authenticated' : authStatus === 'disabled' ? 'Unavailable' : 'Required'}
                            </div>
                        )}

                        <ActionBar style={{ justifyContent: 'center' }}>
                            {authStatus === 'ready' ? (
                                <button
                                    onClick={handleContinue}
                                    disabled={!isHealthy}
                                    className={`clause-btn clause-btn-primary ${!isHealthy ? 'is-disabled' : ''}`}
                                >
                                    Continue to Bill Extraction
                                </button>
                            ) : (
                                <button
                                    onClick={() => navigate(STEP_PATHS.LOGIN)}
                                    disabled={!isHealthy}
                                    className={`clause-btn clause-btn-primary ${!isHealthy ? 'is-disabled' : ''}`}
                                >
                                    Sign In
                                </button>
                            )}
                        </ActionBar>
                    </div>
                </SectionCard>
            </div>
        </PageShell>
    );
}

export default ApiCheckPage;
