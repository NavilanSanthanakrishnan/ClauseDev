import React from 'react';
import { useLocation } from 'react-router-dom';
import TopNav from './TopNav';
import WorkflowStageBar from './WorkflowStageBar';

function PageShell({
    title,
    subtitle,
    actions = null,
    topActions = null,
    children,
    rightRail = null,
    mobileDrawer = null,
    contentMaxWidth = null
}) {
    const location = useLocation();
    const showStageBar = !['/', '/login', '/api-check'].includes(location.pathname);
    const rootClass = rightRail
        ? 'clause-page-main clause-page-main-with-rail'
        : 'clause-page-main';

    return (
        <div className="clause-app-shell">
            <TopNav actions={topActions} />
            {showStageBar && <WorkflowStageBar />}

            <main className={rootClass}>
                <div className="clause-page-content" style={contentMaxWidth ? { maxWidth: contentMaxWidth } : undefined}>
                    {(title || subtitle || actions) && (
                        <div className="clause-page-head">
                            <div>
                                {title && <h1 className="clause-page-title">{title}</h1>}
                                {subtitle && <p className="clause-page-subtitle">{subtitle}</p>}
                            </div>
                            {actions && <div className="clause-page-head-actions">{actions}</div>}
                        </div>
                    )}
                    {children}
                </div>

                {rightRail && (
                    <aside className="clause-page-rail">
                        <div className="clause-page-rail-sticky">
                            {rightRail}
                        </div>
                    </aside>
                )}
            </main>

            {mobileDrawer}
        </div>
    );
}

export default PageShell;
