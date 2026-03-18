import type { LucideIcon } from 'lucide-react';
import type { PropsWithChildren, ReactNode } from 'react';

type SectionFrameProps = PropsWithChildren<{
  eyebrow?: string;
  title: string;
  description?: string;
  icon?: LucideIcon;
  actions?: ReactNode;
  className?: string;
}>;

export function SectionFrame({
  eyebrow,
  title,
  description,
  icon: Icon,
  actions,
  className,
  children,
}: SectionFrameProps) {
  return (
    <section className={`section-card${className ? ` ${className}` : ''}`}>
      <div className="section-head">
        <div className="section-title-row">
          {Icon ? (
            <div className="section-icon">
              <Icon size={18} />
            </div>
          ) : null}
          <div>
            {eyebrow ? <div className="page-eyebrow">{eyebrow}</div> : null}
            <h2 className="section-title">{title}</h2>
            {description ? <p className="section-description">{description}</p> : null}
          </div>
        </div>
        {actions ? <div className="section-actions">{actions}</div> : null}
      </div>
      <div className="section-body">{children}</div>
    </section>
  );
}
