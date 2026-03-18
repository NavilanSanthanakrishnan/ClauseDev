import React from 'react';
import { useNavigate } from 'react-router-dom';
import WorkflowActions from '../WorkflowActions';

function TopNav({ actions = null, showWorkflowActions = true }) {
    const navigate = useNavigate();

    return (
        <header className="clause-top-nav">
            <div className="clause-logo-wrap">
                <img
                    src="/logo.png"
                    alt="Clause Logo"
                    className="clause-logo"
                    onClick={() => navigate('/')}
                    onError={(event) => {
                        event.target.style.display = 'none';
                        const fallback = document.createElement('span');
                        fallback.textContent = 'clause';
                        fallback.style.fontSize = '30px';
                        fallback.style.fontWeight = '500';
                        fallback.style.fontFamily = "'Crimson Pro', serif";
                        fallback.style.cursor = 'pointer';
                        fallback.onclick = () => navigate('/');
                        event.target.parentElement.appendChild(fallback);
                    }}
                />
            </div>
            <div className="clause-top-actions">
                {actions}
                {showWorkflowActions && <WorkflowActions />}
            </div>
        </header>
    );
}

export default TopNav;
