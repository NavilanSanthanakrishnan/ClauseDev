import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
    STAGE_BAR_ITEMS,
    getStageNavigationState,
    getStageKeyForPath,
    getStageStatus
} from '../../utils/workflowStageStatus';
import { useWorkflowState } from '../../hooks/useWorkflowState';

function WorkflowStageBar() {
    const navigate = useNavigate();
    const location = useLocation();
    const { workflow } = useWorkflowState();

    const activeStageKey = getStageKeyForPath(location.pathname);

    const handleStageClick = (stageKey) => {
        const { route, locked } = getStageNavigationState(workflow, stageKey);
        if (locked) return;
        navigate(route);
    };

    return (
        <div className="clause-stage-bar-wrap">
            <div className="clause-stage-bar">
                {STAGE_BAR_ITEMS.map((stage) => {
                    const status = getStageStatus(workflow, stage.key);
                    const { locked } = getStageNavigationState(workflow, stage.key);
                    return (
                        <button
                            key={stage.key}
                            type="button"
                            className={`clause-stage-pill ${activeStageKey === stage.key ? 'is-active' : ''} ${locked ? 'is-disabled' : ''}`}
                            onClick={() => handleStageClick(stage.key)}
                            aria-current={activeStageKey === stage.key ? 'step' : undefined}
                            disabled={locked}
                            aria-disabled={locked}
                            title={locked ? 'Complete previous steps to unlock this stage' : undefined}
                        >
                            <span className={`clause-stage-dot status-${status}`} />
                            <span className="clause-stage-label">{stage.label}</span>
                        </button>
                    );
                })}
            </div>
        </div>
    );
}

export default WorkflowStageBar;
