import React from 'react';

function SectionCard({ title, subtitle, actions = null, children, style = {} }) {
    return (
        <section className="clause-section-card" style={style}>
            {(title || subtitle || actions) && (
                <div className="clause-section-head">
                    <div>
                        {title && <h3 className="clause-section-title">{title}</h3>}
                        {subtitle && <p className="clause-section-subtitle">{subtitle}</p>}
                    </div>
                    {actions && <div>{actions}</div>}
                </div>
            )}
            <div className="clause-section-body">
                {children}
            </div>
        </section>
    );
}

export default SectionCard;
