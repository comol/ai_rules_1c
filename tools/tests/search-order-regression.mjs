// Run against the rendered Claude Code plugin. Regex graders see one compact
// JSON event per line, including multiple tool_use blocks in an assistant turn.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const outputDir = process.argv[2];
const scenarios = {
  s001: 'mcp__plugin_gates_1c-graph-metadata-mcp__search_code',
  s002: 'mcp__plugin_gates_1c-code-metadata-mcp__get_module_structure',
  s003: 'mcp__plugin_gates_1c-code-metadata-mcp__search_function',
};

function assistant(...content) {
  return JSON.stringify({ type: 'assistant', message: { content } });
}

function call(name, input) {
  return { type: 'tool_use', id: 'tool-1', name, input };
}

for (const [id, mcp] of Object.entries(scenarios)) {
  const dir = join(outputDir, 'cases', id + '-g-search-first', 'graders');
  const grader = readFileSync(join(dir, 'search-order.md'), 'utf8');
  assert.match(grader, /^target: trace$/m);
  const pattern = new RegExp(grader.match(/^pattern: '(.*)'$/m)[1]);
  const lookup = call(mcp, { query: 'Find target' });
  const read = call('Read', { file_path: 'CommonModules/Test/Ext/Module.bsl' });
  const rules = assistant(call('Read', { file_path: '.claude/rules-1c/mcp-policy.md' }),
    call('Glob', { pattern: '.claude/skills/**' }), call('Read', { file_path: '.dev.env' }));
  const partialResult = JSON.stringify({ type: 'user', message: { content: [
    { type: 'tool_result', tool_use_id: lookup.id, content: 'No exact match in the index' },
  ] } });
  const accepted = (...events) => pattern.test(events.join('\n'));
  assert.ok(accepted(rules, assistant(lookup)), id + ': MCP-only answer');
  assert.ok(accepted(assistant(lookup), partialResult, assistant(read)), id + ': fallback after MCP');
  for (const native of [read, call('Glob', { pattern: '**/*.bsl' }),
    call('Grep', { pattern: 'memory.md|[а-я]{1,4}', path: 'CommonModules' })]) {
    assert.ok(!accepted(rules, assistant(native, lookup)), id + ': premature ' + native.name);
    assert.ok(accepted(rules, assistant(lookup, native)), id + ': ordered ' + native.name);
  }
  const reordered = { input: read.input, name: 'Read', id: read.id, type: 'tool_use' };
  assert.ok(!accepted(assistant(reordered), assistant(lookup)), id + ': reordered event keys');
  assert.ok(!accepted(assistant({ type: 'text', text: JSON.stringify(lookup) }), assistant(read)),
    id + ': quoted tool name is not a call');
}
console.log('Conditional search order passed for S001, S002 and S003.');
