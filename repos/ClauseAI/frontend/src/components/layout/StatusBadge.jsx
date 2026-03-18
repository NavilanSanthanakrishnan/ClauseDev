import React from 'react';

const STATUS_TONE = {
    completed: { background: '#E8F5E9', color: '#166534', border: '#B7E3C1' },
    running: { background: '#FFF8E1', color: '#8A5A2E', border: '#EAD9BC' },
    loading: { background: '#FFF8E1', color: '#8A5A2E', border: '#EAD9BC' },
    failed: { background: '#FFE9E7', color: '#B42318', border: '#F5C3BE' },
    idle: { background: '#F5F1EA', color: '#6B5444', border: '#E3D7C8' }
};

function StatusBadge({ value = 'idle' }) {
    const key = String(value || 'idle').toLowerCase();
    const tone = STATUS_TONE[key] || STATUS_TONE.idle;

    return (
        <span
            className="clause-status-badge"
            style={{
                backgroundColor: tone.background,
                color: tone.color,
                borderColor: tone.border
            }}
        >
            {value}
        </span>
    );
}

export default StatusBadge;
