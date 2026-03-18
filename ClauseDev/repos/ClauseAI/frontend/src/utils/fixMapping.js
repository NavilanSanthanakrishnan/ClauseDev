const clip = (value, max = 280) => {
    const text = typeof value === 'string' ? value.trim() : '';
    if (!text) return '';
    if (text.length <= max) return text;
    return `${text.slice(0, max - 1)}...`;
};

const toText = (value) => {
    if (value == null) return '';
    if (typeof value === 'string') return value.trim();
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    return '';
};

const getPatchPreview = (change) => {
    const text = toText(change);
    if (!text) {
        return {
            hunkHeader: '',
            beforeSnippet: '',
            afterSnippet: '',
            patchSnippet: ''
        };
    }

    const lines = text.split('\n').map((line) => line.trimEnd()).filter(Boolean);
    const hunkHeader = lines.find((line) => line.startsWith('@@')) || '';
    const beforeSnippet = lines.find((line) => line.startsWith('-') && !line.startsWith('---')) || '';
    const afterSnippet = lines.find((line) => line.startsWith('+') && !line.startsWith('+++')) || '';
    const patchSnippet = clip(lines.slice(0, 6).join('\n'), 420);

    return {
        hunkHeader,
        beforeSnippet: beforeSnippet ? clip(beforeSnippet.slice(1)) : '',
        afterSnippet: afterSnippet ? clip(afterSnippet.slice(1)) : '',
        patchSnippet
    };
};

const getFallbackSnippet = (item) => {
    const explanation = toText(item?.explanation)
        || toText(item?.metadata?.explanation)
        || toText(item?.summary)
        || toText(item?.description)
        || toText(item?.change);
    return clip(explanation);
};

const toFixViewModel = (source, item, idx, titleResolver, whyResolver, riskResolver) => {
    const title = clip(titleResolver(item) || `Fix ${idx + 1}`, 160);
    const why = clip(whyResolver(item) || 'Fix details are still being finalized.', 460);
    const riskOrImpact = clip(riskResolver(item), 120);
    const patch = getPatchPreview(item?.change);

    return {
        id: `${source}-${idx}-${title.slice(0, 40).replace(/\s+/g, '-')}`,
        sourceIndex: idx,
        source,
        title,
        why,
        beforeSnippet: patch.beforeSnippet,
        afterSnippet: patch.afterSnippet,
        hunkHeader: patch.hunkHeader,
        patchSnippet: patch.patchSnippet,
        riskOrImpact,
        fallbackSnippet: getFallbackSnippet(item),
        raw: item
    };
};

const ensureArray = (value) => (Array.isArray(value) ? value : []);

const normalizeIndices = (value, max) => {
    const seen = new Set();
    const result = [];

    ensureArray(value).forEach((raw) => {
        const idx = Number(raw);
        if (!Number.isInteger(idx) || idx < 0 || idx >= max || seen.has(idx)) return;
        seen.add(idx);
        result.push(idx);
    });

    return result.sort((a, b) => a - b);
};

const normalizeInvalidImprovements = (value) => {
    return ensureArray(value).filter((entry) => entry && typeof entry === 'object');
};

export const normalizeFixClassificationPayload = (payload, fallbackImprovements = []) => {
    const source = payload && typeof payload === 'object' ? payload : {};
    const improvements = Array.isArray(source.improvements)
        ? source.improvements
        : ensureArray(fallbackImprovements);

    const invalidImprovements = normalizeInvalidImprovements(
        source.invalidImprovements || source.invalid_improvements
    );

    let validImprovementIndices = normalizeIndices(
        source.validImprovementIndices || source.valid_improvement_indices,
        improvements.length
    );

    if (validImprovementIndices.length === 0 && improvements.length > 0) {
        const invalidIndexSet = new Set(
            invalidImprovements
                .map((entry) => entry?.index)
                .filter((idx) => Number.isInteger(idx) && idx >= 0 && idx < improvements.length)
        );
        validImprovementIndices = improvements
            .map((_, idx) => idx)
            .filter((idx) => !invalidIndexSet.has(idx));
    }

    const validImprovements = validImprovementIndices.map((idx) => improvements[idx]).filter(Boolean);
    const validationSummary = source.validationSummary || source.validation_summary || {
        total: improvements.length,
        valid: validImprovementIndices.length,
        invalid: invalidImprovements.length
    };

    return {
        improvements,
        validImprovements,
        validImprovementIndices,
        invalidImprovements,
        validationSummary,
        warning: source.warning || null
    };
};
