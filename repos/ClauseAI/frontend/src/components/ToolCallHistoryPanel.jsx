import React, { useMemo } from 'react';

const STATUS_STYLES = {
    completed: { background: '#E8F5E9', color: '#166534', border: '#B7E3C1' },
    executing: { background: '#FFF8E1', color: '#7C5B36', border: '#EAD9BC' },
    failed: { background: '#FFE9E7', color: '#B42318', border: '#F5C3BE' }
};

const formatJson = (value) => {
    if (value == null) return '';
    if (typeof value === 'string') {
        try {
            const parsed = JSON.parse(value);
            return JSON.stringify(parsed, null, 2);
        } catch {
            return value;
        }
    }
    try {
        return JSON.stringify(value, null, 2);
    } catch {
        return String(value);
    }
};

const getPreviewText = (value) => {
    const text = formatJson(value);
    if (!text) return '';
    if (text.length <= 160) return text;
    return `${text.slice(0, 160)}...`;
};

const toLabel = (key) =>
    String(key)
        .replace(/_/g, ' ')
        .trim()
        .replace(/\b\w/g, (letter) => letter.toUpperCase());

const parseMaybeJson = (value) => {
    if (value == null) return null;
    if (typeof value !== 'string') return value;
    const text = value.trim();
    if (!text) return null;
    try {
        return JSON.parse(text);
    } catch {
        return value;
    }
};

const primitiveText = (value) => {
    if (value == null) return 'N/A';
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (typeof value === 'number') return String(value);
    const normalized = String(value).trim();
    return normalized || 'N/A';
};

function StructuredView({ value, depth = 0 }) {
    if (value == null) {
        return <div className="clause-struct-value">No data</div>;
    }

    if (typeof value !== 'object') {
        return <div className="clause-struct-value">{primitiveText(value)}</div>;
    }

    if (Array.isArray(value)) {
        if (value.length === 0) {
            return <div className="clause-struct-value">No entries</div>;
        }

        return (
            <div className="clause-struct-grid">
                {value.slice(0, 8).map((item, idx) => (
                    <div key={`array-item-${idx}`} className="clause-struct-row">
                        <div className="clause-struct-key">Item {idx + 1}</div>
                        <div className="clause-struct-value">
                            {typeof item === 'object'
                                ? <StructuredView value={item} depth={depth + 1} />
                                : primitiveText(item)}
                        </div>
                    </div>
                ))}
                {value.length > 8 && (
                    <div className="clause-struct-value">+{value.length - 8} more entries</div>
                )}
            </div>
        );
    }

    const entries = Object.entries(value);
    if (entries.length === 0) {
        return <div className="clause-struct-value">No fields</div>;
    }

    return (
        <div className="clause-struct-grid">
            {entries.slice(0, 14).map(([key, entryValue]) => {
                const hasNested = entryValue && typeof entryValue === 'object';
                return (
                    <div key={key} className="clause-struct-row">
                        <div className="clause-struct-key">{toLabel(key)}</div>
                        <div className="clause-struct-value">
                            {!hasNested && primitiveText(entryValue)}
                            {hasNested && depth < 2 && (
                                <details>
                                    <summary className="clause-raw-summary">
                                        {Array.isArray(entryValue) ? `${entryValue.length} items` : 'Open section'}
                                    </summary>
                                    <StructuredView value={entryValue} depth={depth + 1} />
                                </details>
                            )}
                            {hasNested && depth >= 2 && (
                                <span>{Array.isArray(entryValue) ? `[Array(${entryValue.length})]` : '[Object]'}</span>
                            )}
                        </div>
                    </div>
                );
            })}
            {entries.length > 14 && (
                <div className="clause-struct-value">+{entries.length - 14} more fields</div>
            )}
        </div>
    );
}

function ToolCallHistoryPanel({ toolHistory = [], currentToolCall = null, title = 'Tool Calls' }) {
    const entries = useMemo(() => {
        const history = Array.isArray(toolHistory) ? toolHistory : [];
        const current = currentToolCall && currentToolCall.tool_name
            ? [{ ...currentToolCall, status: currentToolCall.status || 'executing', _current: true }]
            : [];
        return [...history, ...current];
    }, [toolHistory, currentToolCall]);

    if (entries.length === 0) return null;

    return (
        <div className="clause-tool-panel" style={{ maxHeight: '440px', overflowY: 'auto' }}>
            <div style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#8B7355', marginBottom: '12px' }}>
                {title}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {entries.map((tool, idx) => {
                    const status = tool.status || 'completed';
                    const statusStyle = STATUS_STYLES[status] || STATUS_STYLES.executing;
                    const inputData = parseMaybeJson(tool.tool_args || tool.tool_input || {});
                    const outputData = parseMaybeJson(tool.result || tool.tool_output || '');
                    const inputPretty = formatJson(inputData || {});
                    const outputPretty = formatJson(outputData || '');
                    const outputAvailable = Boolean(outputPretty) && status !== 'executing';
                    const duration = typeof tool.duration === 'number' ? `${tool.duration.toFixed(2)}s` : null;

                    return (
                        <div key={`${tool.tool_name || 'tool'}-${tool.iteration || 0}-${idx}`} className="clause-tool-item">
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                                <div>
                                    <div style={{ fontSize: '12px', fontWeight: 600, color: '#1C1C1C' }}>
                                        {tool.tool_name || 'Unknown Tool'}
                                    </div>
                                    <div style={{ fontSize: '10px', color: '#8B7355' }}>
                                        Iteration {tool.iteration || 1}{duration ? ` • ${duration}` : ''}
                                    </div>
                                </div>
                                <span style={{
                                    fontSize: '10px',
                                    fontWeight: 700,
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.08em',
                                    padding: '3px 8px',
                                    borderRadius: '4px',
                                    backgroundColor: statusStyle.background,
                                    color: statusStyle.color,
                                    border: `1px solid ${statusStyle.border}`
                                }}>
                                    {status}
                                </span>
                            </div>

                            <div style={{ fontSize: '11px', color: '#6B5444', marginBottom: '6px' }}>
                                Output preview: {outputAvailable ? getPreviewText(outputPretty) : 'Waiting for tool result...'}
                            </div>

                            <details>
                                <summary className="clause-raw-summary">
                                    Input Fields
                                </summary>
                                <StructuredView value={inputData || {}} />
                            </details>

                            <details style={{ marginTop: '8px' }}>
                                <summary className="clause-raw-summary" style={{ cursor: outputAvailable ? 'pointer' : 'not-allowed' }}>
                                    Output {outputAvailable ? '(click to view)' : '(pending)'}
                                </summary>
                                {outputAvailable && (
                                    <>
                                        <StructuredView value={outputData} />
                                        <details style={{ marginTop: '8px' }}>
                                            <summary className="clause-raw-summary">Raw JSON</summary>
                                            <pre className="clause-raw-json">{outputPretty}</pre>
                                        </details>
                                    </>
                                )}
                            </details>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export default ToolCallHistoryPanel;
