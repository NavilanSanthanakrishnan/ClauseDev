import React from 'react';
import MarkdownRenderer from '../MarkdownRenderer';

function BillReportView({ reportText }) {
    return (
        <div style={{
            background: '#FDFCF8',
            border: '1px solid #EAE3D5',
            borderRadius: '4px',
            padding: '32px',
            marginBottom: '32px'
        }}>
            <div style={{
                background: 'white',
                border: '1px solid #EAE3D5',
                borderRadius: '4px',
                padding: '24px'
            }}>
                <MarkdownRenderer markdown={reportText} />
            </div>
        </div>
    );
}

export default BillReportView;
