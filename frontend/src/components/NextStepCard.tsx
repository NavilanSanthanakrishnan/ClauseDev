import type { LucideIcon } from 'lucide-react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

type NextStepCardProps = {
  to: string;
  title: string;
  description: string;
  icon: LucideIcon;
  direction?: 'next' | 'previous';
};

export function NextStepCard({
  to,
  title,
  description,
  icon: Icon,
  direction = 'next',
}: NextStepCardProps) {
  const ArrowIcon = direction === 'next' ? ArrowRight : ArrowLeft;

  return (
    <Link to={to} className={`next-step-card ${direction}`}>
      <div className="next-step-top">
        <span>{direction === 'next' ? 'Next Page' : 'Previous Page'}</span>
        <ArrowIcon size={16} />
      </div>
      <div className="next-step-title-row">
        <div className="next-step-icon">
          <Icon size={18} />
        </div>
        <div>
          <div className="next-step-title">{title}</div>
          <div className="next-step-description">{description}</div>
        </div>
      </div>
    </Link>
  );
}
