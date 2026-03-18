import React from 'react';

const styles = {
    h1: { fontFamily: "'Crimson Pro', serif", fontSize: '34px', fontWeight: 600, color: '#1C1C1C', margin: '30px 0 14px' },
    h2: { fontFamily: "'Crimson Pro', serif", fontSize: '26px', fontWeight: 600, color: '#1C1C1C', margin: '24px 0 12px' },
    h3: { fontFamily: "'Crimson Pro', serif", fontSize: '20px', fontWeight: 600, color: '#1C1C1C', margin: '20px 0 10px' },
    p: { fontSize: '14px', color: '#5B4638', lineHeight: '1.75', margin: '0 0 14px' },
    list: { margin: '0 0 14px 20px', color: '#5B4638' },
    li: { fontSize: '14px', lineHeight: '1.7', marginBottom: '6px' },
    blockquote: { borderLeft: '3px solid #D2AE84', margin: '0 0 16px', padding: '6px 0 6px 12px', color: '#5B4638', fontSize: '14px', lineHeight: '1.7' },
    pre: { backgroundColor: '#FCFAF6', border: '1px solid #EAE3D5', borderRadius: '6px', padding: '14px', margin: '0 0 16px', overflowX: 'auto', fontSize: '12px', lineHeight: '1.6', color: '#374151', fontFamily: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace" },
    hr: { border: 0, borderTop: '1px solid #EAE3D5', margin: '18px 0' },
    code: { backgroundColor: '#FCFAF6', border: '1px solid #EAE3D5', borderRadius: '4px', padding: '1px 5px', fontSize: '12px', color: '#374151', fontFamily: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace" },
    link: { color: '#8A5A2E', textDecoration: 'underline' }
};

const tokenizeInline = (text, keyPrefix) => {
    if (!text) return null;
    const regex = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^\)]+\)|\*[^*]+\*)/g;
    const parts = [];
    let lastIndex = 0;
    let match;
    let index = 0;

    while ((match = regex.exec(text)) !== null) {
        if (match.index > lastIndex) {
            parts.push(<React.Fragment key={`${keyPrefix}-txt-${index}`}>{text.slice(lastIndex, match.index)}</React.Fragment>);
            index += 1;
        }

        const token = match[0];
        if (token.startsWith('**') && token.endsWith('**')) {
            parts.push(<strong key={`${keyPrefix}-strong-${index}`}>{token.slice(2, -2)}</strong>);
        } else if (token.startsWith('*') && token.endsWith('*')) {
            parts.push(<em key={`${keyPrefix}-em-${index}`}>{token.slice(1, -1)}</em>);
        } else if (token.startsWith('`') && token.endsWith('`')) {
            parts.push(<code key={`${keyPrefix}-code-${index}`} style={styles.code}>{token.slice(1, -1)}</code>);
        } else {
            const linkMatch = token.match(/^\[([^\]]+)\]\(([^\)]+)\)$/);
            if (linkMatch) {
                const [, label, href] = linkMatch;
                const isSafe = href.startsWith('http://') || href.startsWith('https://') || href.startsWith('mailto:');
                if (isSafe) {
                    parts.push(
                        <a key={`${keyPrefix}-link-${index}`} href={href} target="_blank" rel="noopener noreferrer" style={styles.link}>
                            {label}
                        </a>
                    );
                } else {
                    parts.push(<React.Fragment key={`${keyPrefix}-raw-${index}`}>{label}</React.Fragment>);
                }
            }
        }

        lastIndex = regex.lastIndex;
        index += 1;
    }

    if (lastIndex < text.length) {
        parts.push(<React.Fragment key={`${keyPrefix}-tail`}>{text.slice(lastIndex)}</React.Fragment>);
    }

    return parts;
};

function MarkdownRenderer({ markdown }) {
    if (!markdown) return null;

    const lines = markdown.replace(/\r\n/g, '\n').split('\n');
    const blocks = [];
    let inCode = false;
    let codeLines = [];

    lines.forEach((line) => {
        if (line.trim().startsWith('```')) {
            if (!inCode) {
                inCode = true;
                codeLines = [];
            } else {
                blocks.push({ type: 'code', text: codeLines.join('\n') });
                inCode = false;
                codeLines = [];
            }
            return;
        }

        if (inCode) {
            codeLines.push(line);
            return;
        }

        if (/^###\s+/.test(line)) {
            blocks.push({ type: 'h3', text: line.replace(/^###\s+/, '') });
            return;
        }
        if (/^##\s+/.test(line)) {
            blocks.push({ type: 'h2', text: line.replace(/^##\s+/, '') });
            return;
        }
        if (/^#\s+/.test(line)) {
            blocks.push({ type: 'h1', text: line.replace(/^#\s+/, '') });
            return;
        }
        if (/^>\s?/.test(line)) {
            blocks.push({ type: 'blockquote', text: line.replace(/^>\s?/, '') });
            return;
        }
        if (/^---+$/.test(line.trim())) {
            blocks.push({ type: 'hr' });
            return;
        }
        if (/^\d+\.\s+/.test(line)) {
            blocks.push({ type: 'ol-item', text: line.replace(/^\d+\.\s+/, '') });
            return;
        }
        if (/^[-*]\s+/.test(line)) {
            blocks.push({ type: 'ul-item', text: line.replace(/^[-*]\s+/, '') });
            return;
        }

        blocks.push({ type: 'p', text: line });
    });

    if (inCode) {
        blocks.push({ type: 'code', text: codeLines.join('\n') });
    }

    const rendered = [];
    let pendingListType = null;
    let pendingItems = [];

    const flushList = (key) => {
        if (!pendingListType || pendingItems.length === 0) return;
        const ListTag = pendingListType === 'ol-item' ? 'ol' : 'ul';
        rendered.push(
            <ListTag key={`list-${key}`} style={styles.list}>
                {pendingItems.map((item, idx) => (
                    <li key={`li-${key}-${idx}`} style={styles.li}>{tokenizeInline(item, `li-${key}-${idx}`)}</li>
                ))}
            </ListTag>
        );
        pendingListType = null;
        pendingItems = [];
    };

    blocks.forEach((block, idx) => {
        if (block.type === 'ol-item' || block.type === 'ul-item') {
            if (pendingListType && pendingListType !== block.type) {
                flushList(`swap-${idx}`);
            }
            pendingListType = block.type;
            pendingItems.push(block.text);
            return;
        }

        flushList(idx);

        if (block.type === 'h1') rendered.push(<h1 key={`h1-${idx}`} style={styles.h1}>{tokenizeInline(block.text, `h1-${idx}`)}</h1>);
        else if (block.type === 'h2') rendered.push(<h2 key={`h2-${idx}`} style={styles.h2}>{tokenizeInline(block.text, `h2-${idx}`)}</h2>);
        else if (block.type === 'h3') rendered.push(<h3 key={`h3-${idx}`} style={styles.h3}>{tokenizeInline(block.text, `h3-${idx}`)}</h3>);
        else if (block.type === 'blockquote') rendered.push(<blockquote key={`bq-${idx}`} style={styles.blockquote}>{tokenizeInline(block.text, `bq-${idx}`)}</blockquote>);
        else if (block.type === 'code') rendered.push(<pre key={`pre-${idx}`} style={styles.pre}><code>{block.text}</code></pre>);
        else if (block.type === 'hr') rendered.push(<hr key={`hr-${idx}`} style={styles.hr} />);
        else if (block.text?.trim()) rendered.push(<p key={`p-${idx}`} style={styles.p}>{tokenizeInline(block.text, `p-${idx}`)}</p>);
    });

    flushList('end');

    return <div>{rendered}</div>;
}

export default MarkdownRenderer;
