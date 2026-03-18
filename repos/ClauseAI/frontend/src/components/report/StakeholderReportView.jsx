import React from 'react';

const POWER_COLORS = {
    HIGH: '#F8D7DA',
    MEDIUM: '#FFF3CD',
    LOW: '#D4EDDA'
};

const POSITION_COLORS = {
    STRONG_OPPOSITION: '#FFE5E5',
    MODERATE_TO_STRONG_OPPOSITION: '#FFE5E5',
    MODERATE_OPPOSITION: '#FFF3E0',
    NEUTRAL: '#F5F5F5',
    SUPPORT: '#E8F5E9',
    STRONG_SUPPORT: '#E8F5E9'
};

function StakeholderReportView({ structuredData, analysisText }) {
    const stakeholderData = structuredData?.stakeholder_analysis || structuredData?.structured_data?.stakeholder_analysis || structuredData?.stakeholder_analysis;
    const industries = stakeholderData?.affected_industries || [];

    const sortedStakeholders = [...industries].sort((a, b) => {
        const positionOrder = {
            STRONG_OPPOSITION: 0,
            MODERATE_TO_STRONG_OPPOSITION: 1,
            MODERATE_OPPOSITION: 2,
            NEUTRAL: 3,
            SUPPORT: 4,
            STRONG_SUPPORT: 5
        };
        return (positionOrder[a.likely_position] || 99) - (positionOrder[b.likely_position] || 99);
    });

    const getPositionBadgeStyle = (position) => {
        const backgroundColor = POSITION_COLORS[position] || '#F5F5F5';
        const isOpposition = position?.includes('OPPOSITION');
        const isSupport = position?.includes('SUPPORT');
        const color = isOpposition ? '#DC3545' : isSupport ? '#28A745' : '#6C757D';

        return {
            padding: '4px 12px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 700,
            textTransform: 'uppercase',
            backgroundColor,
            color,
            border: `1px solid ${color}40`
        };
    };

    const getPowerBadgeStyle = (power) => {
        const backgroundColor = POWER_COLORS[power] || '#F5F5F5';
        const colorMap = {
            HIGH: '#DC3545',
            MEDIUM: '#FFC107',
            LOW: '#28A745'
        };
        const color = colorMap[power] || '#6C757D';

        return {
            padding: '4px 12px',
            borderRadius: '4px',
            fontSize: '10px',
            fontWeight: 700,
            textTransform: 'uppercase',
            backgroundColor,
            color,
            border: `1px solid ${color}40`
        };
    };

    return (
        <>
            {(stakeholderData?.total_estimated_affected_entities || industries.length) && (
                <div style={{
                    background: 'white',
                    border: '1px solid #EAE3D5',
                    borderRadius: '4px',
                    padding: '24px',
                    marginBottom: '24px',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: '24px'
                }}>
                    <div>
                        <div style={{
                            fontSize: '13px',
                            fontWeight: 600,
                            color: '#8B7355',
                            textTransform: 'uppercase',
                            marginBottom: '8px'
                        }}>
                            Total Affected Entities
                        </div>
                        <div style={{
                            fontFamily: "'Crimson Pro', serif",
                            fontSize: '32px',
                            fontWeight: 600,
                            color: '#1C1C1C'
                        }}>
                            {stakeholderData.total_estimated_affected_entities || '—'}
                        </div>
                    </div>
                    <div>
                        <div style={{
                            fontSize: '13px',
                            fontWeight: 600,
                            color: '#8B7355',
                            textTransform: 'uppercase',
                            marginBottom: '8px'
                        }}>
                            Industries Analyzed
                        </div>
                        <div style={{
                            fontFamily: "'Crimson Pro', serif",
                            fontSize: '32px',
                            fontWeight: 600,
                            color: '#1C1C1C'
                        }}>
                            {industries.length}
                        </div>
                    </div>
                </div>
            )}

            {sortedStakeholders.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {sortedStakeholders.map((stakeholder, idx) => (
                        <div key={idx} style={{
                            background: 'white',
                            border: '1px solid #EAE3D5',
                            borderRadius: '4px',
                            padding: '24px'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                                <div style={{ flex: 1 }}>
                                    <h3 style={{
                                        fontFamily: "'Crimson Pro', serif",
                                        fontSize: '28px',
                                        fontWeight: 600,
                                        color: '#1C1C1C',
                                        marginBottom: '8px'
                                    }}>
                                        {stakeholder.industry}
                                    </h3>
                                    <div style={{ fontSize: '14px', color: '#6B5444', fontStyle: 'italic' }}>
                                        {stakeholder.estimated_entities_affected}
                                    </div>
                                </div>

                                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'flex-end' }}>
                                    <span style={getPowerBadgeStyle(stakeholder.lobbying_power)}>
                                        {stakeholder.lobbying_power} Power
                                    </span>
                                    <span style={getPositionBadgeStyle(stakeholder.likely_position)}>
                                        {stakeholder.likely_position?.replace(/_/g, ' ')}
                                    </span>
                                </div>
                            </div>

                            {stakeholder.key_concerns && stakeholder.key_concerns.length > 0 && (
                                <div>
                                    <div style={{
                                        fontSize: '12px',
                                        fontWeight: 600,
                                        color: '#8B7355',
                                        marginBottom: '8px'
                                    }}>
                                        Key Concerns
                                    </div>
                                    <ul style={{ margin: 0, paddingLeft: '20px' }}>
                                        {stakeholder.key_concerns.slice(0, 3).map((concern, concernIdx) => (
                                            <li key={concernIdx} style={{ fontSize: '13px', color: '#374151', lineHeight: '1.6' }}>
                                                {concern}
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {analysisText && (
                <div style={{
                    background: 'white',
                    border: '1px solid #EAE3D5',
                    borderRadius: '4px',
                    padding: '24px',
                    marginTop: '24px'
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

export default StakeholderReportView;
