export type BillRecord = {
  id: string;
  state: string;
  title: string;
  summary: string;
  excerpt: string;
  tags: string[];
  status: string;
  sponsor: string;
  committee: string;
  whyMatched: string[];
};

export const mockBills: BillRecord[] = [
  {
    id: 'GA-HB-1234',
    state: 'Georgia',
    title: 'Healthcare Payment Reform Act',
    summary:
      'Establishes bundled payment requirements for state Medicaid programs and requires participating hospitals to accept single payments covering all listed services.',
    excerpt:
      'All healthcare providers shall implement episode-based payment models for procedures listed in Appendix A by January 1, 2026.',
    tags: ['bundled payment', 'healthcare', 'compliance'],
    status: 'In Committee',
    sponsor: 'Rep. Holloway',
    committee: 'Health',
    whyMatched: [
      'Strong lexical match for bundled payment language',
      'High semantic overlap with Medicaid reimbursement policy',
      'Committee path aligns with healthcare finance bills',
    ],
  },
  {
    id: 'AL-SB-567',
    state: 'Alabama',
    title: 'Medicare Advantage Bundling Standards',
    summary:
      'Mandates pricing transparency for bundled payment arrangements in Medicare Advantage plans operating in Alabama.',
    excerpt:
      'Bundled payment arrangements must disclose component pricing within 30 days of patient request.',
    tags: ['bundled payment', 'healthcare', 'transparency'],
    status: 'Passed Senate',
    sponsor: 'Sen. Archer',
    committee: 'Insurance',
    whyMatched: [
      'Cross-state policy pattern is highly similar',
      'Exact terminology match on bundled payment',
      'Comparable disclosure and reimbursement structure',
    ],
  },
  {
    id: 'CO-SB-184',
    state: 'Colorado',
    title: 'Consumer Data Broker Accountability Act',
    summary:
      'Creates registration, deletion, and opt-out requirements for consumer data brokers and expands attorney general enforcement authority.',
    excerpt:
      'A data broker shall maintain a public mechanism allowing a consumer to request deletion of covered personal information.',
    tags: ['privacy', 'data broker', 'consumer protection'],
    status: 'Passed',
    sponsor: 'Sen. Alvarez',
    committee: 'Judiciary',
    whyMatched: [
      'Strong privacy-policy semantic alignment',
      'Outcome-relevant peer bill for passed-state comparison',
      'Frequently cited by similar state privacy measures',
    ],
  },
];

