type StatusBadgeProps = {
  children: string;
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info';
};

function inferTone(value: string): StatusBadgeProps['tone'] {
  const normalized = value.toLowerCase();

  if (
    normalized.includes('complete')
    || normalized.includes('accept')
    || normalized.includes('enacted')
    || normalized.includes('ready')
  ) {
    return 'success';
  }

  if (
    normalized.includes('run')
    || normalized.includes('pending')
    || normalized.includes('processing')
    || normalized.includes('passed')
  ) {
    return 'warning';
  }

  if (
    normalized.includes('fail')
    || normalized.includes('reject')
    || normalized.includes('error')
    || normalized.includes('veto')
  ) {
    return 'danger';
  }

  if (normalized.includes('draft') || normalized.includes('info')) {
    return 'info';
  }

  return 'neutral';
}

export function StatusBadge({ children, tone }: StatusBadgeProps) {
  const finalTone = tone ?? inferTone(children);

  return <span className={`status-badge ${finalTone}`}>{children}</span>;
}
