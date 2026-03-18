import React from 'react';
import { resetWorkflow } from '../../utils/workflowStorage';
import { createLogger } from '../../utils/logger';

const logger = createLogger('AppErrorBoundary');

class AppErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            hasError: false,
            message: ''
        };
    }

    static getDerivedStateFromError(error) {
        return {
            hasError: true,
            message: error?.message || 'Unexpected frontend error'
        };
    }

    componentDidCatch(error, errorInfo) {
        logger.error('Route-level rendering error', {
            error,
            componentStack: errorInfo?.componentStack
        });
    }

    handleReload = () => {
        window.location.reload();
    };

    handleResetAndReload = () => {
        resetWorkflow();
        window.location.assign('/');
    };

    render() {
        if (!this.state.hasError) {
            return this.props.children;
        }

        return (
            <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#f5f2ed', padding: '24px' }}>
                <div style={{ maxWidth: '720px', width: '100%', background: '#FDFCF8', border: '1px solid #EAE3D5', borderRadius: '8px', padding: '28px' }}>
                    <h1 style={{ margin: '0 0 10px 0', fontFamily: "'Crimson Pro', serif", fontSize: '34px', color: '#1C1C1C' }}>
                        Frontend Error
                    </h1>
                    <p style={{ margin: '0 0 18px 0', color: '#6B5444', fontSize: '14px' }}>
                        The page encountered a render error. You can reload or reset local workflow state and reload.
                    </p>
                    <div style={{ marginBottom: '18px', background: '#FEF2F2', border: '1px solid #F5C3BE', borderRadius: '6px', padding: '10px 12px', fontSize: '12px', color: '#B42318' }}>
                        {this.state.message}
                    </div>
                    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                        <button className="clause-btn clause-btn-primary" onClick={this.handleReload}>
                            Reload
                        </button>
                        <button className="clause-btn clause-btn-secondary" onClick={this.handleResetAndReload}>
                            Reset Workflow & Reload
                        </button>
                    </div>
                </div>
            </div>
        );
    }
}

export default AppErrorBoundary;

