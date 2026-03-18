import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const API_BASE = 'http://127.0.0.1:8001/api';
const ROOT = path.resolve(__dirname, '..', '..');
const CASES_PATH = path.join(ROOT, 'artifacts', 'qa', 'accuracy_cases.json');
const REPORT_PATH = path.join(ROOT, 'artifacts', 'qa', 'accuracy_report.json');

type AccuracyCase = {
  kind: string;
  endpoint: string;
  query: string;
  filters: Record<string, unknown>;
  expected_id: string;
  expected_rank_max: number;
};

type CaseResult = {
  kind: string;
  endpoint: string;
  query: string;
  expected_id: string;
  expected_rank_max: number;
  actual_rank: number | null;
  passed: boolean;
  top_ids: string[];
  transport_error?: string;
};

function readCases(): AccuracyCase[] {
  const payload = JSON.parse(fs.readFileSync(CASES_PATH, 'utf-8')) as { cases: AccuracyCase[] };
  return payload.cases;
}

async function loginToken(request: { post: Function }) {
  const response = await request.post(`${API_BASE}/auth/login`, {
    data: {
      email: 'access@clause.local',
      password: 'ClauseDemo!2026',
    },
  });
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  return String(payload.token);
}

function evaluateCase(searchCase: AccuracyCase, items: Array<Record<string, unknown>>): CaseResult {
  const ids = items.map((item) => String(item.bill_id ?? item.document_id ?? ''));
  const rank = ids.findIndex((item) => item === searchCase.expected_id);
  const actualRank = rank === -1 ? null : rank + 1;
  return {
    kind: searchCase.kind,
    endpoint: searchCase.endpoint,
    query: searchCase.query,
    expected_id: searchCase.expected_id,
    expected_rank_max: searchCase.expected_rank_max,
    actual_rank: actualRank,
    passed: actualRank !== null && actualRank <= searchCase.expected_rank_max,
    top_ids: ids.slice(0, 5),
  };
}

test('login screen renders', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
});

test('500 retrieval accuracy cases', async ({ request }) => {
  test.setTimeout(2_700_000);
  const token = await loginToken(request);
  const cases = readCases();
  const results: CaseResult[] = [];

  for (const searchCase of cases) {
    try {
      const response = await request.post(`${API_BASE}${searchCase.endpoint}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        data: {
          query: searchCase.query,
          filters: searchCase.filters,
        },
        timeout: 90_000,
      });
      if (!response.ok()) {
        results.push({
          kind: searchCase.kind,
          endpoint: searchCase.endpoint,
          query: searchCase.query,
          expected_id: searchCase.expected_id,
          expected_rank_max: searchCase.expected_rank_max,
          actual_rank: null,
          passed: false,
          top_ids: [],
          transport_error: `${response.status()} ${response.statusText()}`,
        });
        continue;
      }
      const payload = await response.json();
      results.push(evaluateCase(searchCase, payload.items ?? []));
    } catch (error) {
      results.push({
        kind: searchCase.kind,
        endpoint: searchCase.endpoint,
        query: searchCase.query,
        expected_id: searchCase.expected_id,
        expected_rank_max: searchCase.expected_rank_max,
        actual_rank: null,
        passed: false,
        top_ids: [],
        transport_error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  const passed = results.filter((item) => item.passed);
  const byKind = Object.fromEntries(
    [...new Set(results.map((item) => item.kind))].map((kind) => {
      const subset = results.filter((item) => item.kind === kind);
      const subsetPassed = subset.filter((item) => item.passed).length;
      return [kind, { passed: subsetPassed, total: subset.length, accuracy: subsetPassed / subset.length }];
    }),
  );

  const report = {
    total: results.length,
    passed: passed.length,
    accuracy: passed.length / results.length,
    byKind,
    failures: results.filter((item) => !item.passed).slice(0, 100),
  };
  fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
  fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2));

  expect(results.length).toBe(500);
  expect(report.accuracy).toBeGreaterThanOrEqual(0.9);
});
