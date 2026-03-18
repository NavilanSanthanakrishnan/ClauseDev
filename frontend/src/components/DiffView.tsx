type Props = { diff: string };

/**
 * Renders a unified diff with colour-coded +/- lines,
 * matching the style of Claude Code / git diffs.
 */
export function DiffView({ diff }: Props) {
  if (!diff?.trim()) return null;

  const lines = diff.split('\n');

  return (
    <div className="diff-view">
      {lines.map((line, i) => {
        const ch = line[0];
        let cls = 'diff-line';
        if (ch === '+') cls += ' diff-add';
        else if (ch === '-') cls += ' diff-remove';
        else if (ch === '@') cls += ' diff-hunk';
        else cls += ' diff-ctx';

        return (
          <div key={i} className={cls}>
            <span className="diff-gutter">
              {ch === '+' ? '+' : ch === '-' ? '−' : ch === '@' ? '⋯' : ' '}
            </span>
            <span className="diff-text">
              {ch === '+' || ch === '-' ? line.slice(1) : line}
            </span>
          </div>
        );
      })}
    </div>
  );
}
