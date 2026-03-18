import React from 'react';

const RISK_COLORS = {
    HIGH: '#DC3545',
    MEDIUM: '#FFC107',
    LOW: '#28A745'
};

function LegalReportView({ structuredData, analysisText }) {
    const getRiskBadgeStyle = (riskLevel) => {
        const color = RISK_COLORS[riskLevel] || '#6C757D';
        return {
            padding: '4px 12px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 700,
            textTransform: 'uppercase',
            backgroundColor: `${color}20`,
            color,
            border: `1px solid ${color}`
        };
    };

    return (
        <>
            <div style={{ marginBottom: '32px' }}>
                <h2 style={{
                    fontFamily: "'Crimson Pro', serif",
                    fontSize: '32px',
                    fontWeight: 600,
                    color: '#1C1C1C',
                    marginBottom: '20px'
                }}>
                    Preemption & Statutory Conflicts
                </h2>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {(structuredData?.external_conflicts || []).map((conflict, idx) => (
                        <div key={idx} style={{
                            background: 'white',
                            border: '1px solid #EAE3D5',
                            borderLeft: `4px solid ${RISK_COLORS[conflict.risk_level]}`,
                            borderRadius: '4px',
                            padding: '24px'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                                <div>
                                    <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: '#8B7355', marginBottom: '8px', letterSpacing: '0.5px' }}>
                                        {conflict.type}
                                    </div>
                                    <h3 style={{ fontFamily: "'Crimson Pro', serif", fontSize: '20px', fontWeight: 600, color: '#1C1C1C', margin: 0 }}>
                                        {conflict.conflicting_statute}
                                    </h3>
                                </div>
                                <span style={getRiskBadgeStyle(conflict.risk_level)}>{conflict.risk_level}</span>
                            </div>
                            <div style={{ fontSize: '14px', color: '#1C1C1C', lineHeight: '1.7' }}>{conflict.explanation}</div>
                        </div>
                    ))}
                </div>
            </div>

            <div style={{ marginBottom: '32px' }}>
                <h2 style={{
                    fontFamily: "'Crimson Pro', serif",
                    fontSize: '32px',
                    fontWeight: 600,
                    color: '#1C1C1C',
                    marginBottom: '20px'
                }}>
                    Constitutional Issues
                </h2>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {(structuredData?.constitutional_issues || []).map((issue, idx) => (
                        <div key={idx} style={{
                            background: 'white',
                            border: '1px solid #EAE3D5',
                            borderLeft: `4px solid ${RISK_COLORS[issue.risk_level]}`,
                            borderRadius: '4px',
                            padding: '24px'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                                <div>
                                    <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: '#8B7355', marginBottom: '8px', letterSpacing: '0.5px' }}>
                                        {issue.type}
                                    </div>
                                    <h3 style={{ fontFamily: "'Crimson Pro', serif", fontSize: '18px', fontWeight: 600, color: '#1C1C1C', margin: 0 }}>
                                        Issue ID: {issue.issue_id}
                                    </h3>
                                </div>
                                <span style={getRiskBadgeStyle(issue.risk_level)}>{issue.risk_level}</span>
                            </div>
                            <div style={{ fontSize: '14px', color: '#1C1C1C', lineHeight: '1.7' }}>{issue.explanation}</div>
                        </div>
                    ))}
                </div>
            </div>

            {analysisText && (
                <div style={{
                    background: 'white',
                    border: '1px solid #EAE3D5',
                    borderRadius: '4px',
                    padding: '24px',
                    marginBottom: '32px'
                }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#1C1C1C', marginBottom: '12px' }}>
                        Full Model Output
                    </h3>
                    <div style={{
                        fontSize: '12px',
                        color: '#6B5444',
                        whiteSpace: 'pre-wrap',
                        lineHeight: '1.6',
                        maxHeight: '300px',
                        overflowY: 'auto'
                    }}>
                        {analysisText}
                    </div>
                </div>
            )}
        </>
    );
}

export default LegalReportView;
