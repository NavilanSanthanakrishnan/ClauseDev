/**
* Unified hunk patch application helpers for fixes/improvements.
*/

const HUNK_HEADER_REGEX = /^@@\s-(\d+)(?:,(\d+))?\s\+(\d+)(?:,(\d+))?\s@@/;

const toLines = (text) => {
    if (!text) return [];
    return String(text).replace(/\r\n/g, '\n').split('\n');
};

const lineIndexToChar = (lines, lineIndex) => {
    const target = Math.max(0, Math.min(lineIndex, lines.length));
    let total = 0;
    for (let i = 0; i < target; i += 1) {
        total += lines[i].length;
        if (i < lines.length - 1) total += 1;
    }
    return total;
};

const parsePatchHunks = (change) => {
    if (typeof change !== 'string' || !change.trim()) {
        throw new Error('change must be a non-empty patch string');
    }

    const lines = change.replace(/\r\n/g, '\n').split('\n');
    const hunks = [];
    let current = null;

    for (const line of lines) {
        if (!line.trim() && !current) {
            continue;
        }

        if (line.startsWith('@@ ')) {
            const match = line.match(HUNK_HEADER_REGEX);
            if (!match) {
                throw new Error(`Invalid hunk header: ${line}`);
            }
            if (current) {
                hunks.push(current);
            }
            current = {
                header: line,
                oldStart: Number(match[1]),
                oldCount: match[2] ? Number(match[2]) : 1,
                newStart: Number(match[3]),
                newCount: match[4] ? Number(match[4]) : 1,
                lines: []
            };
            continue;
        }

        if (!current) {
            throw new Error('Patch text must start with a valid @@ hunk header');
        }

        // Be lenient with trailing/empty lines inside a hunk.
        if (!line.trim()) {
            continue;
        }

        if (line.startsWith('\\')) {
            continue;
        }

        const prefix = line[0] || '';
        if (![' ', '+', '-'].includes(prefix)) {
            // Tolerate model output where context lines are missing the
            // required leading space prefix and treat them as context lines.
            current.lines.push(` ${line}`);
            continue;
        }
        current.lines.push(line);
    }

    if (current) {
        hunks.push(current);
    }

    if (hunks.length === 0) {
        throw new Error('Patch must contain at least one @@ hunk header');
    }

    const hasPatchLines = hunks.some((hunk) => hunk.lines.some((line) => line.startsWith('+') || line.startsWith('-')));
    if (!hasPatchLines) {
        throw new Error('Patch must contain at least one + or - line');
    }

    return hunks;
};

const buildHunkLines = (hunk, reverse = false) => {
    const oldLines = [];
    const newLines = [];

    hunk.lines.forEach((line) => {
        const prefix = line[0];
        const content = line.slice(1);
        const effectivePrefix = reverse
            ? (prefix === '+' ? '-' : prefix === '-' ? '+' : prefix)
            : prefix;

        if (effectivePrefix === ' ') {
            oldLines.push(content);
            newLines.push(content);
        } else if (effectivePrefix === '-') {
            oldLines.push(content);
        } else if (effectivePrefix === '+') {
            newLines.push(content);
        }
    });

    return { oldLines, newLines };
};

const matchesAt = (lines, start, expected) => {
    if (start < 0 || start + expected.length > lines.length) return false;
    for (let i = 0; i < expected.length; i += 1) {
        if (lines[start + i] !== expected[i]) return false;
    }
    return true;
};

const normalizeForMatch = (value) => String(value || '').replace(/\s+/g, ' ').trim();

const matchesAtNormalized = (lines, start, expected) => {
    if (start < 0 || start + expected.length > lines.length) return false;
    for (let i = 0; i < expected.length; i += 1) {
        if (normalizeForMatch(lines[start + i]) !== normalizeForMatch(expected[i])) return false;
    }
    return true;
};

const findBestMatch = (lines, expectedStart, oldLines) => {
    if (oldLines.length === 0) {
        return { start: Math.max(0, Math.min(expectedStart, lines.length)), deleteCount: 0 };
    }

    if (matchesAt(lines, expectedStart, oldLines)) {
        return { start: expectedStart, deleteCount: oldLines.length };
    }

    if (matchesAtNormalized(lines, expectedStart, oldLines)) {
        return { start: expectedStart, deleteCount: oldLines.length };
    }

    const maxOffset = Math.max(lines.length, oldLines.length);
    for (let offset = 1; offset <= maxOffset; offset += 1) {
        const down = expectedStart + offset;
        if (matchesAt(lines, down, oldLines)) {
            return { start: down, deleteCount: oldLines.length };
        }
        if (matchesAtNormalized(lines, down, oldLines)) {
            return { start: down, deleteCount: oldLines.length };
        }
        const up = expectedStart - offset;
        if (matchesAt(lines, up, oldLines)) {
            return { start: up, deleteCount: oldLines.length };
        }
        if (matchesAtNormalized(lines, up, oldLines)) {
            return { start: up, deleteCount: oldLines.length };
        }
    }

    // Reflow fallback: compare normalized block text against variable-size windows.
    const targetBlock = normalizeForMatch(oldLines.join('\n'));
    const minSpan = Math.max(1, oldLines.length - 6);
    const maxExtraSpan = 6;
    const maxStart = Math.max(0, lines.length - 1);

    let best = null;
    for (let start = 0; start <= maxStart; start += 1) {
        const maxSpan = Math.min(lines.length - start, oldLines.length + maxExtraSpan);
        for (let span = minSpan; span <= maxSpan; span += 1) {
            const candidate = normalizeForMatch(lines.slice(start, start + span).join('\n'));
            if (candidate === targetBlock) {
                const distance = Math.abs(start - expectedStart);
                if (!best || distance < best.distance) {
                    best = { start, deleteCount: span, distance };
                }
            }
        }
    }

    if (best) {
        return { start: best.start, deleteCount: best.deleteCount };
    }

    return null;
};

export const applyUnifiedPatch = (text, change, options = {}) => {
    const { reverse = false } = options;
    const hunks = parsePatchHunks(change);
    const lines = toLines(text);
    let delta = 0;
    let highlight = null;

    hunks.forEach((hunk, index) => {
        const baseStart = reverse ? hunk.newStart : hunk.oldStart;
        const expectedStart = Math.max(0, Math.min(baseStart - 1 + delta, lines.length));
        const { oldLines, newLines } = buildHunkLines(hunk, reverse);

        const match = findBestMatch(lines, expectedStart, oldLines);
        if (!match) {
            throw new Error(`Hunk ${index + 1} could not be applied due to context mismatch`);
        }

        lines.splice(match.start, match.deleteCount, ...newLines);
        delta += newLines.length - match.deleteCount;

        const start = lineIndexToChar(lines, match.start);
        const end = lineIndexToChar(lines, match.start + newLines.length);
        highlight = { start, end };
    });

    return {
        updatedText: lines.join('\n'),
        highlight
    };
};

export const applyChange = (text, improvement) => {
    const patch = improvement?.change;
    if (typeof patch !== 'string' || !patch.trim()) {
        throw new Error('Improvement is missing a valid change patch');
    }
    return applyUnifiedPatch(text, patch, { reverse: false });
};

export const revertChange = (text, improvement) => {
    const patch = improvement?.change;
    if (typeof patch !== 'string' || !patch.trim()) {
        throw new Error('Improvement is missing a valid change patch');
    }
    return applyUnifiedPatch(text, patch, { reverse: true });
};

export const extractOptimizations = (payload) => {
    if (!payload || typeof payload !== 'object') return [];
    if (Array.isArray(payload.improvements)) return payload.improvements;

    const root = payload.structured_data || payload;
    if (!root || typeof root !== 'object') return [];

    if (Array.isArray(root.improvements)) return root.improvements;
    if (Array.isArray(root.language_optimizations)) return root.language_optimizations;
    if (Array.isArray(root.optimization_proposals)) return root.optimization_proposals;
    if (Array.isArray(root.optimizations)) return root.optimizations;
    if (Array.isArray(root.language_changes)) return root.language_changes;
    if (Array.isArray(root.changes)) return root.changes;
    if (Array.isArray(root.diff_proposals)) return root.diff_proposals;

    return [];
};
