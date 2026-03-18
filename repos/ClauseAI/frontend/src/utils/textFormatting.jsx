import React from 'react';

export const renderHighlightedText = (text, highlight) => {
    if (!highlight || highlight.start == null || highlight.end == null) {
        return text;
    }
    const safeStart = Math.max(0, Math.min(text.length, highlight.start));
    const safeEnd = Math.max(safeStart, Math.min(text.length, highlight.end));
    const before = text.slice(0, safeStart);
    const mid = text.slice(safeStart, safeEnd);
    const after = text.slice(safeEnd);
    return (
        <>
            {before}
            <mark style={{ backgroundColor: '#FFF3CD', padding: '0 2px' }}>{mid}</mark>
            {after}
        </>
    );
};
