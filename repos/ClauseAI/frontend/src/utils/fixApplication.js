import { applyChange, extractOptimizations } from './fixChangeApplicator';
import { normalizeFixClassificationPayload } from './fixMapping';

const toSortedArray = (setOrArray) => {
    const values = Array.isArray(setOrArray) ? setOrArray : Array.from(setOrArray || []);
    return values
        .map((value) => Number(value))
        .filter((value) => Number.isInteger(value) && value >= 0)
        .sort((a, b) => a - b);
};

export const getAppliedSetsFromWorkflow = (workflow) => {
    const current = workflow || {};
    return {
        bill: new Set(Array.isArray(current.billFixes?.appliedSet) ? current.billFixes.appliedSet : []),
        legal: new Set(Array.isArray(current.legalFixes?.appliedSet) ? current.legalFixes.appliedSet : []),
        stakeholder: new Set(Array.isArray(current.stakeholderFixes?.appliedSet) ? current.stakeholderFixes.appliedSet : [])
    };
};

const getBaselineBillText = (workflow) => {
    const current = workflow || {};
    const explicitBase = typeof current.fixApplicationBaseText === 'string' ? current.fixApplicationBaseText : '';
    if (explicitBase) return explicitBase;
    if (typeof current.billText === 'string' && current.billText) return current.billText;
    if (typeof current.extraction?.editedText === 'string' && current.extraction.editedText) return current.extraction.editedText;
    return typeof current.extraction?.originalText === 'string' ? current.extraction.originalText : '';
};

const getWorkflowPools = (workflow) => {
    const billClassification = normalizeFixClassificationPayload(
        workflow?.billAnalysis,
        Array.isArray(workflow?.billAnalysis?.directImprovements) ? workflow.billAnalysis.directImprovements : []
    );
    const legalClassification = normalizeFixClassificationPayload(
        workflow?.legalAnalysis,
        Array.isArray(workflow?.legalAnalysis?.structuredData?.legal_improvements)
            ? workflow.legalAnalysis.structuredData.legal_improvements
            : []
    );
    const stakeholderClassification = normalizeFixClassificationPayload(
        workflow?.stakeholderAnalysis,
        extractOptimizations(workflow?.stakeholderAnalysis?.structuredData)
    );

    return {
        bill: billClassification.validImprovements,
        legal: legalClassification.validImprovements,
        stakeholder: stakeholderClassification.validImprovements
    };
};

export const getFixPoolsFromWorkflow = (workflow) => getWorkflowPools(workflow);

export const recomputeBillTextFromAppliedSets = (workflow, appliedSets, poolsOverride = null) => {
    const pools = poolsOverride || getWorkflowPools(workflow);
    const sourceOrder = ['bill', 'legal', 'stakeholder'];
    const errors = [];
    let nextText = getBaselineBillText(workflow);

    sourceOrder.forEach((source) => {
        const sourceFixes = Array.isArray(pools[source]) ? pools[source] : [];
        const indexes = toSortedArray(appliedSets[source]);

        indexes.forEach((idx) => {
            const fix = sourceFixes[idx];
            try {
                nextText = applyChange(nextText, fix).updatedText;
            } catch (error) {
                errors.push(`${source} fix ${idx + 1}: ${error.message || 'Could not apply fix'}`);
            }
        });
    });

    return { billText: nextText, errors };
};
