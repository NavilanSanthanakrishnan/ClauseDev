import { useEffect, useState } from 'react';
import {
    getWorkflow,
    isWorkflowHydrated,
    WORKFLOW_HYDRATED_EVENT,
    WORKFLOW_UPDATED_EVENT
} from '../utils/workflowStorage';

export function useWorkflowState() {
    const [workflow, setWorkflow] = useState(() => getWorkflow());
    const [hydrated, setHydrated] = useState(() => isWorkflowHydrated());

    useEffect(() => {
        const handleWorkflowUpdated = (event) => {
            setWorkflow(event?.detail || getWorkflow());
        };
        const handleHydrated = () => {
            setHydrated(true);
            setWorkflow(getWorkflow());
        };

        window.addEventListener(WORKFLOW_UPDATED_EVENT, handleWorkflowUpdated);
        window.addEventListener(WORKFLOW_HYDRATED_EVENT, handleHydrated);

        return () => {
            window.removeEventListener(WORKFLOW_UPDATED_EVENT, handleWorkflowUpdated);
            window.removeEventListener(WORKFLOW_HYDRATED_EVENT, handleHydrated);
        };
    }, []);

    return { workflow, hydrated };
}

