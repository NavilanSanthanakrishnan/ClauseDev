import { useCallback, useRef, useState } from 'react';
import { API_CONFIG } from '../config/api';
import { useTaskPolling } from './useTaskPolling';

export const TWO_PHASE_STATE = {
    ANALYZING_REPORT: 'analyzing_report',
    REPORT_READY: 'report_ready',
    GENERATING_FIXES: 'generating_fixes',
    ERROR: 'error'
};

export function useTwoPhaseAnalysis({
    pollInterval = API_CONFIG.POLL_INTERVAL,
    report,
    fixes
} = {}) {
    const [currentState, setCurrentState] = useState(TWO_PHASE_STATE.ANALYZING_REPORT);

    const reportPolling = useTaskPolling({
        intervalMs: pollInterval,
        start: report?.start,
        status: report?.status,
        result: report?.result,
        onPartial: report?.onPartial,
        onStatus: report?.onStatus
    });

    const fixesPolling = useTaskPolling({
        intervalMs: pollInterval,
        start: fixes?.start,
        status: fixes?.status,
        result: fixes?.result,
        onPartial: fixes?.onPartial,
        onStatus: fixes?.onStatus
    });

    const reportRef = useRef(report);
    reportRef.current = report;
    const fixesRef = useRef(fixes);
    fixesRef.current = fixes;

    const runReportPhase = useCallback(async (options = {}) => {
        setCurrentState(TWO_PHASE_STATE.ANALYZING_REPORT);
        const outcome = await reportPolling.run({
            ...options,
            initialOperation: reportRef.current?.initialOperation || 'Generating report...'
        });

        if (outcome?.ok) {
            try {
                if (typeof reportRef.current?.onCompleted === 'function') {
                    reportRef.current.onCompleted(outcome.data, outcome);
                }
                setCurrentState(TWO_PHASE_STATE.REPORT_READY);
            } catch (completedError) {
                const message = completedError?.message || 'Report phase failed';
                reportPolling.setError(message);
                if (typeof reportRef.current?.onFailed === 'function') {
                    reportRef.current.onFailed({ ...outcome, ok: false, error: message });
                }
                setCurrentState(TWO_PHASE_STATE.ERROR);
                return { ...outcome, ok: false, error: message };
            }
        } else if (!outcome?.cancelled) {
            if (typeof reportRef.current?.onFailed === 'function') {
                reportRef.current.onFailed(outcome);
            }
            setCurrentState(TWO_PHASE_STATE.ERROR);
        }

        return outcome;
    }, [reportPolling]);

    const runFixesPhase = useCallback(async (options = {}) => {
        setCurrentState(TWO_PHASE_STATE.GENERATING_FIXES);
        const outcome = await fixesPolling.run({
            ...options,
            initialOperation: fixesRef.current?.initialOperation || 'Generating fixes...'
        });

        if (outcome?.ok) {
            try {
                if (typeof fixesRef.current?.onCompleted === 'function') {
                    fixesRef.current.onCompleted(outcome.data, outcome);
                }
                if (typeof fixesRef.current?.onSuccessState === 'string') {
                    setCurrentState(fixesRef.current.onSuccessState);
                } else {
                    setCurrentState(TWO_PHASE_STATE.REPORT_READY);
                }
            } catch (completedError) {
                const message = completedError?.message || 'Fixes phase failed';
                fixesPolling.setError(message);
                if (typeof fixesRef.current?.onFailed === 'function') {
                    fixesRef.current.onFailed({ ...outcome, ok: false, error: message });
                }
                setCurrentState(TWO_PHASE_STATE.REPORT_READY);
                return { ...outcome, ok: false, error: message };
            }
        } else if (!outcome?.cancelled) {
            if (typeof fixesRef.current?.onFailed === 'function') {
                fixesRef.current.onFailed(outcome);
            }
            setCurrentState(TWO_PHASE_STATE.REPORT_READY);
        }

        return outcome;
    }, [fixesPolling]);

    const error = fixesPolling.error || reportPolling.error || null;
    const progress = currentState === TWO_PHASE_STATE.GENERATING_FIXES ? fixesPolling.progress : reportPolling.progress;
    const operation = currentState === TWO_PHASE_STATE.GENERATING_FIXES ? fixesPolling.operation : reportPolling.operation;

    const setCombinedError = useCallback((value) => {
        reportPolling.setError(value);
        fixesPolling.setError(value);
    }, [fixesPolling.setError, reportPolling.setError]);

    return {
        currentState,
        setCurrentState,
        runReportPhase,
        runFixesPhase,
        progress,
        operation,
        error,
        reportTaskState: reportPolling.taskState,
        fixesTaskState: fixesPolling.taskState,
        setError: setCombinedError
    };
}
