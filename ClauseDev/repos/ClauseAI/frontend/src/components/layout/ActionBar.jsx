import React from 'react';

function ActionBar({ children, style = {} }) {
    return (
        <div className="clause-action-bar" style={style}>
            {children}
        </div>
    );
}

export default ActionBar;
