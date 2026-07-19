import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import { adaptAnalysisResponse } from '../src/contracts/responseAdapter.js';


const fixture = name => JSON.parse(readFileSync(
  new URL(`../src/mocks/${name}`, import.meta.url),
  'utf8',
));

const filesUnder = directory => readdirSync(directory).flatMap(name => {
  const path = `${directory}/${name}`;
  return statSync(path).isDirectory() ? filesUnder(path) : [path];
});

test('frontend adapter accepts every public Companion response type', () => {
  const cases = [
    ['initial_analysis_response.json', 'initial_analysis'],
    ['plan_generation_response.json', 'plan_generation'],
    ['followup_evaluation_response.json', 'followup_evaluation'],
  ];
  for (const [name, kind] of cases) {
    assert.equal(adaptAnalysisResponse(fixture(name)).kind, kind);
  }
});

test('production bundle contains no LLM credential or internal worker configuration', () => {
  const dist = fileURLToPath(new URL('../dist', import.meta.url)).replaceAll('\\', '/');
  const bundle = filesUnder(dist).map(path => readFileSync(path, 'utf8')).join('\n');
  for (const forbidden of ['GEMINI_API_KEY', 'LLM_API_KEY', 'AI_WORKER_URL']) {
    assert.equal(bundle.includes(forbidden), false, `${forbidden} leaked into frontend bundle`);
  }
  assert.equal(/AIza[0-9A-Za-z_-]{30,}/.test(bundle), false, 'Gemini credential pattern leaked into frontend bundle');
});
