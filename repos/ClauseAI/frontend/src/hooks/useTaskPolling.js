import { useCallback, useEffect, useRef, useState } from 'react';

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function useTaskPolling({
    intervalMs = 1500,
    maxIntervalMs = 15000,
    backoffMultiplier = 2,
    jitterMs = 250,
    statusNotFoundRetries = 5,
    statusNotFoundRetryDelayMs = 400,
    start,
    status,
    result,
    onPartial,
    onStatus,
    onBeforeRun,
    onAfterRun
} = {}) {
    const mountedRef = useRef(true);
    const runTokenRef = useRef(0);

    const [taskState, setTaskState] = useState('idle');
    const [progress, setProgress] = useState(null);
    const [operation, setOperation] = useState('Initializing...');
    const [error, setError] = useState(null);

    useEffect(() => {
        return () => {
            mountedRef.current = false;
            runTokenRef.current += 1;
        };
    }, []);

    const run = useCallback(async ({
        existingRequestId = null,
        startArgs = null,
        startIfMissing = true,
        initialOperation = 'Initializing...'
    } = {}) => {
        const runToken = runTokenRef.current + 1;
        runTokenRef.current = runToken;

        const isCancelled = () => !mountedRef.current || runTokenRef.current !== runToken;

        setTaskState('running');
        setError(null);
        setProgress(null);
        setOperation(initialOperation);

        if (typeof onBeforeRun === 'function') {
            onBeforeRun();
        }

        let requestId = existingRequestId;

        try {
            if (!requestId && startIfMissing && typeof start === 'function') {
                const startResponse = await start(startArgs);
                if (isCancelled()) return { cancelled: true };
                requestId = startResponse?.request_id || requestId;
            }

            if (!requestId) {
                throw new Error('Missing request id for task polling');
            }

            let terminalStatus = null;
            let statusNotFoundCount = 0;
            let backoffIntervalMs = intervalMs;
            while (true) {
                let snapshot;
                try {
                    snapshot = await status(requestId);
                    statusNotFoundCount = 0;
                    backoffIntervalMs = intervalMs;
                } catch (statusError) {
                    const isNotFound = statusError?.statusCode === 404;
                    const isRateLimited = statusError?.statusCode === 429;
                    if (isNotFound && statusNotFoundCount < statusNotFoundRetries) {
                        statusNotFoundCount += 1;
                        const notFoundJitter = jitterMs > 0 ? Math.floor(Math.random() * Math.min(100, jitterMs)) : 0;
                        const retryDelay = Math.max(
                            100,
                            Math.min(intervalMs, statusNotFoundRetryDelayMs) + notFoundJitter
                        );
                        await sleep(retryDelay);
                        if (isCancelled()) return { cancelled: true, requestId };
                        continue;
                    }
                    if (isRateLimited) {
                        const jitter = jitterMs > 0 ? Math.floor(Math.random() * jitterMs) : 0;
                        backoffIntervalMs = Math.min(
                            maxIntervalMs,
                            Math.max(intervalMs, Math.floor(backoffIntervalMs * backoffMultiplier) + jitter)
                        );
                        setOperation('Rate limited, retrying...');
                        await sleep(backoffIntervalMs);
                        if (isCancelled()) return { cancelled: true, requestId };
                        continue;
                    }
                    throw statusError;
                }
                if (isCancelled()) return { cancelled: true, requestId };

                const hasProgress = typeof snapshot?.progress === 'number';
                setProgress(hasProgress ? snapshot.progress : null);
                setOperation(snapshot?.current_operation || initialOperation);

                if (typeof onStatus === 'function') {
                    onStatus(snapshot, { requestId });
                }

                if (typeof onPartial === 'function') {
                    onPartial(snapshot?.partial_data, snapshot, { requestId });
                }

                if (snapshot?.status === 'completed' || snapshot?.status === 'failed') {
                    terminalStatus = snapshot;
                    break;
                }

                await sleep(backoffIntervalMs);
                if (isCancelled()) return { cancelled: true, requestId };
            }

            if (!terminalStatus || terminalStatus.status === 'failed') {
                const message = terminalStatus?.error || terminalStatus?.data?.Error || 'Task failed';
                setError(message);
                setTaskState('failed');
                if (typeof onAfterRun === 'function') {
                    onAfterRun({ ok: false, error: message, requestId, terminalStatus });
                }
                return { ok: false, error: message, requestId, terminalStatus };
            }

            let finalData = terminalStatus?.data;
            if (!finalData && typeof result === 'function') {
                const resultPayload = await result(requestId);
                if (isCancelled()) return { cancelled: true, requestId };
                if (resultPayload?.status === 'failed') {
                    const message = resultPayload?.error || resultPayload?.data?.Error || 'Task failed';
                    setError(message);
                    setTaskState('failed');
                    if (typeof onAfterRun === 'function') {
                        onAfterRun({ ok: false, error: message, requestId, terminalStatus: resultPayload });
                    }
                    return { ok: false, error: message, requestId, terminalStatus: resultPayload };
                }
                finalData = resultPayload?.data;
            }

            setTaskState('completed');
            if (typeof onAfterRun === 'function') {
                onAfterRun({ ok: true, data: finalData, requestId, terminalStatus });
            }
            return { ok: true, data: finalData, requestId, terminalStatus };
        } catch (runError) {
            if (isCancelled()) return { cancelled: true, requestId };
            const message = runError?.message || 'Task failed';
            setError(message);
            setTaskState('failed');
            if (typeof onAfterRun === 'function') {
                onAfterRun({ ok: false, error: message, requestId, terminalStatus: null });
            }
            return { ok: false, error: message, requestId, terminalStatus: null };
        }
    }, [
        backoffMultiplier,
        intervalMs,
        jitterMs,
        maxIntervalMs,
        onAfterRun,
        onBeforeRun,
        onPartial,
        onStatus,
        result,
        start,
        status,
        statusNotFoundRetryDelayMs,
        statusNotFoundRetries
    ]);

    const cancel = useCallback(() => {
        runTokenRef.current += 1;
        setTaskState('idle');
    }, []);

    return {
        run,
        cancel,
        taskState,
        progress,
        operation,
        error,
        setError
    };
}
