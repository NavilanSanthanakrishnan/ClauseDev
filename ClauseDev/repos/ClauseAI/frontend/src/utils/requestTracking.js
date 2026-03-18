import { getWorkflow, updateWorkflow } from './workflowStorage';

export const setRequestTracking = (key, requestId, status) => {
    const workflow = getWorkflow();
    const current = workflow.requestTracking?.[key];
    if (current?.requestId === requestId && current?.status === status) {
        return;
    }
    updateWorkflow({
        requestTracking: {
            ...workflow.requestTracking,
            [key]: { requestId, status }
        }
    });
};
