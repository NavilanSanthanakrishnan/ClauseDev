import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { archiveWorkflow, resetWorkflow, resetStepByPath } from '../utils/workflowStorage';

function WorkflowActions() {
    const location = useLocation();
    const navigate = useNavigate();

    const handleRedo = () => {
        const confirmed = window.confirm(
            'Redo this step? This will clear data from this step and downstream steps. You can keep navigating without resetting by using the stage bar.'
        );
        if (!confirmed) return;

        resetStepByPath(location.pathname);
        navigate(location.pathname, {
            replace: true,
            state: {
                ...(location.state || {}),
                redoNonce: Date.now()
            }
        });
    };

    const handleRestart = () => {
        archiveWorkflow(undefined, 'restart');
        resetWorkflow();
        navigate('/', { replace: true });
    };

    return (
        <div className="clause-workflow-actions">
            <button
                onClick={handleRedo}
                className="clause-btn clause-btn-soft"
            >
                Redo Step
            </button>
            <button
                onClick={handleRestart}
                className="clause-btn clause-btn-primary"
            >
                Restart Workflow
            </button>
        </div>
    );
}

export default WorkflowActions;
