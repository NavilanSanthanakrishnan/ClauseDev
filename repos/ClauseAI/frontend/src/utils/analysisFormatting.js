const TOOL_ARTIFACT_PATTERN = /<tool_call>|<function=|<parameter=/i;

const isPrimitive = (value) =>
    value == null || ['string', 'number', 'boolean'].includes(typeof value);

const humanizeKey = (key) =>
    String(key)
        .replace(/_/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .replace(/\b\w/g, (char) => char.toUpperCase());

const primitiveToText = (value) => {
    if (value == null) return 'N/A';
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (typeof value === 'number') return Number.isFinite(value) ? String(value) : 'N/A';
    const text = String(value).trim();
    return text.length > 0 ? text : 'N/A';
};

const toStructuredMarkdown = (structured, heading = 'Structured Analysis') => {
    if (!structured || typeof structured !== 'object') return '';

    const lines = [`## ${heading}`];
    const visited = new WeakSet();

    const pushNode = (label, value, depth = 0) => {
        if (depth > 4) {
            lines.push(`- **${label}:** [Truncated]`);
            return;
        }

        if (isPrimitive(value)) {
            lines.push(`- **${label}:** ${primitiveToText(value)}`);
            return;
        }

        if (Array.isArray(value)) {
            const sectionLevel = '#'.repeat(Math.min(6, depth + 3));
            lines.push(`${sectionLevel} ${label} (${value.length})`);

            if (value.length === 0) {
                lines.push('- No entries.');
                return;
            }

            const limit = Math.min(value.length, 8);
            for (let idx = 0; idx < limit; idx += 1) {
                const item = value[idx];
                if (isPrimitive(item)) {
                    lines.push(`${idx + 1}. ${primitiveToText(item)}`);
                    continue;
                }

                lines.push(`### Item ${idx + 1}`);
                if (item && typeof item === 'object') {
                    if (visited.has(item)) {
                        lines.push('- Circular reference omitted.');
                        continue;
                    }
                    visited.add(item);
                    Object.entries(item).forEach(([entryKey, entryValue]) => {
                        pushNode(humanizeKey(entryKey), entryValue, depth + 1);
                    });
                } else {
                    lines.push(`- ${primitiveToText(item)}`);
                }
            }

            if (value.length > limit) {
                lines.push(`- ...and ${value.length - limit} more entries.`);
            }
            return;
        }

        if (typeof value === 'object') {
            if (visited.has(value)) {
                lines.push(`- **${label}:** [Circular reference omitted]`);
                return;
            }
            visited.add(value);

            const sectionLevel = '#'.repeat(Math.min(6, depth + 3));
            lines.push(`${sectionLevel} ${label}`);
            const entries = Object.entries(value);
            if (entries.length === 0) {
                lines.push('- No fields.');
                return;
            }

            entries.forEach(([entryKey, entryValue]) => {
                pushNode(humanizeKey(entryKey), entryValue, depth + 1);
            });
            return;
        }

        lines.push(`- **${label}:** ${primitiveToText(value)}`);
    };

    Object.entries(structured).forEach(([key, value]) => {
        pushNode(humanizeKey(key), value, 0);
    });

    return lines.join('\n');
};

export const sanitizeAnalysisForDisplay = (analysis, structured, heading) => {
    const normalizedHeading = heading || 'Structured Analysis';
    if (typeof analysis !== 'string' || analysis.trim().length === 0) {
        return toStructuredMarkdown(structured, normalizedHeading);
    }

    if (TOOL_ARTIFACT_PATTERN.test(analysis) && structured && typeof structured === 'object') {
        return toStructuredMarkdown(structured, normalizedHeading);
    }

    return analysis;
};
