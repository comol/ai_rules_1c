// support-guard.mjs — experimental Claude Code PreToolUse hook, off unless the project opts in.
// Applies the vendor-support guard of the 1c-metadata-manage tools to a raw Edit / Write /
// MultiEdit of a configuration dump, which the in-tool guard never sees.
//
// Port of hooks/support-guard.mjs and hooks/common/support-state.mjs of
// https://github.com/Nikolay-Shirokov/cc-1c-skills (MIT) at 2e75b0f483eb020e9f09562d1a7be1982bc5ac6e;
// licence text: NOTICE.md next to this file.
// Local:
//   - opt-in: does nothing unless the nearest .dev.env has SUPPORT_GUARD_HOOK=on;
//   - reaction from .dev.env SUPPORT_GUARD (deny | warn | off; empty or invalid = deny);
//     .v8-project.json is not read;
//   - support state decoded exactly as Assert-EditAllowed of the vendored PowerShell tools:
//     root uuid and external-object root from the first element child of the document element,
//     and a present Ext/ParentConfigurations.bin that cannot be read or parsed (32 bytes or
//     less included) gets the same reaction as a locked object (fail-closed);
//   - only files of the dump are checked (Configuration.xml, ConfigDumpInfo.xml, Ext/ and the
//     metadata collection folders of the configuration root), so notes next to a dump are free;
//   - warn and every notice go to the user as systemMessage (stderr of exit 0 is not shown);
//   - any other error lets the edit through with a one-line notice.
//
// stdin: PreToolUse JSON { tool_name, tool_input, cwd, ... }. stdout: nothing (allow) or one JSON
// object. Exit code is always 0. Requires Node 18+.

import { readFileSync, existsSync, statSync, openSync, readSync, closeSync } from 'node:fs';
import { dirname, join, resolve, isAbsolute, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const NOTICE = '[support-guard]';

// Top-level folders of a configuration dump (1C configuration XML format, 8.3–8.5).
const DUMP_COLLECTIONS = new Set([
  'Languages', 'Subsystems', 'StyleItems', 'Styles', 'CommonPictures', 'SessionParameters', 'Roles',
  'CommonTemplates', 'FilterCriteria', 'CommonModules', 'CommonAttributes', 'ExchangePlans',
  'XDTOPackages', 'WebServices', 'HTTPServices', 'WSReferences', 'EventSubscriptions', 'ScheduledJobs',
  'SettingsStorages', 'FunctionalOptions', 'FunctionalOptionsParameters', 'DefinedTypes', 'Bots',
  'PaletteColors', 'CommonCommands', 'CommandGroups', 'Constants', 'CommonForms', 'Catalogs', 'Documents',
  'DocumentNumerators', 'Sequences', 'DocumentJournals', 'Enums', 'Reports', 'DataProcessors',
  'InformationRegisters', 'AccumulationRegisters', 'ChartsOfCharacteristicTypes', 'ChartsOfAccounts',
  'AccountingRegisters', 'ChartsOfCalculationTypes', 'CalculationRegisters', 'BusinessProcesses', 'Tasks',
  'ExternalDataSources', 'IntegrationServices',
]);
const DUMP_ROOT_ENTRIES = new Set(['Configuration.xml', 'ConfigDumpInfo.xml', 'Ext']);
const WIN = process.platform === 'win32';

// ---------------------------------------------------------------- .dev.env (DevEnv.ps1 contract)

// Nearest .dev.env walking up from startDir, at most 20 levels; null when absent.
export function findDevEnvFile(startDir) {
  let d = startDir;
  for (let i = 0; i < 20 && d; i++) {
    const candidate = join(d, '.dev.env');
    try { if (statSync(candidate).isFile()) return candidate; } catch { /* absent */ }
    const parent = dirname(d);
    if (parent === d) break;
    d = parent;
  }
  return null;
}

// First KEY=value line wins; value trimmed, one pair of matching quotes removed; '' when unset.
export function devEnvValue(file, name) {
  if (!file) return '';
  try {
    const text = readFileSync(file, 'utf8').replace(/^\uFEFF/, '');
    for (const raw of text.split(/\r?\n/)) {
      const line = raw.trimStart();
      if (!line.trim() || line.startsWith('#')) continue;
      const m = /^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(line);
      if (!m || m[1] !== name) continue;
      let value = m[2].trim();
      if (value.length >= 2 && ((value[0] === '"' && value.endsWith('"')) || (value[0] === "'" && value.endsWith("'")))) {
        value = value.slice(1, -1).trim();
      }
      return value;
    }
  } catch { /* unreadable = not configured */ }
  return '';
}

export function hookEnabled(file) {
  return devEnvValue(file, 'SUPPORT_GUARD_HOOK').toLowerCase() === 'on';
}

// Same values as the in-tool guard; anything else (empty included) is deny.
export function guardMode(file) {
  const mode = devEnvValue(file, 'SUPPORT_GUARD').toLowerCase();
  return ['deny', 'warn', 'off'].includes(mode) ? mode : 'deny';
}

// ---------------------------------------------------------------- dump XML (Get-RootUuid contract)

function isFile(p) { try { return statSync(p).isFile(); } catch { return false; } }
function isDir(p) { try { return statSync(p).isDirectory(); } catch { return false; } }

function readHead(p, bytes = 65536) {
  const fd = openSync(p, 'r');
  try {
    const buf = Buffer.alloc(bytes);
    const n = readSync(fd, buf, 0, bytes, 0);
    return buf.subarray(0, n).toString('utf8');
  } finally { closeSync(fd); }
}

// First element child of the document element: { localName, uuid } or null. The PowerShell guard
// reads `$xml.DocumentElement.FirstChild` (skipping non-element nodes) and its `uuid` attribute;
// a file that is not XML (a module, a picture) gives null there and here. Unlike [xml], the rest of
// the document is not checked for well-formedness: a broken file may still yield its uuid here.
export function firstChildElement(path) {
  try {
    if (!isFile(path)) return null;
    let s = readHead(path).replace(/^\uFEFF/, '');
    if (!/^\s*</.test(s)) return null;
    // Prolog, comments, processing instructions and CDATA are not elements.
    s = s.replace(/<\?[\s\S]*?\?>/g, '').replace(/<!--[\s\S]*?-->/g, '').replace(/<!\[CDATA\[[\s\S]*?\]\]>/g, '')
      .replace(/<!DOCTYPE[^>]*>/gi, '');
    const tag = /<([A-Za-z_][\w.\-]*(?::[A-Za-z_][\w.\-]*)?)((?:\s+[^\s=>\/]+\s*=\s*(?:"[^"]*"|'[^']*'))*)\s*(\/?)>/g;
    const root = tag.exec(s);
    if (!root || root[3] === '/') return null;
    const child = tag.exec(s);
    if (!child) return null;
    // Anything but whitespace / text between the two tags that closes the root means no child.
    const between = s.slice(root.index + root[0].length, child.index);
    if (/<\//.test(between)) return null;
    const localName = child[1].includes(':') ? child[1].split(':')[1] : child[1];
    const attr = /(?:^|\s)uuid\s*=\s*(?:"([^"]*)"|'([^']*)')/.exec(child[2]);
    const uuid = attr ? (attr[1] ?? attr[2] ?? '') : '';
    return { localName, uuid: uuid || null };
  } catch {
    return null;
  }
}

export function rootUuid(path) {
  return firstChildElement(path)?.uuid ?? null;
}

// Root file of an autonomous ExternalDataProcessor / ExternalReport dump (cc-1c-skills issue #39).
export function isExternalObjectRoot(path) {
  const el = firstChildElement(path);
  return !!el && (el.localName === 'ExternalDataProcessor' || el.localName === 'ExternalReport');
}

// True when target is a file of the dump rooted at cfgDir rather than something kept beside it.
export function inDumpScope(cfgDir, target) {
  const rel = relative(cfgDir, target);
  if (!rel || rel.startsWith('..') || isAbsolute(rel)) return false;
  const first = rel.split(/[\\/]/)[0];
  return DUMP_ROOT_ENTRIES.has(first) || DUMP_COLLECTIONS.has(first);
}

// ---------------------------------------------------------------- support state (Assert-EditAllowed)

// { status: 'allow' | 'blocked' | 'unknown', code, reason, cfgDir, binPath }.
// require: 'editable' (blocked when the object is locked, f1 = 0) or 'removed' (blocked unless f1 = 2).
export function decideSupport(targetPath, require = 'editable') {
  const allow = (extra = {}) => ({ status: 'allow', code: null, reason: '', cfgDir: null, binPath: null, ...extra });
  const rp = resolve(targetPath);
  if (isExternalObjectRoot(rp)) return allow();
  let elemUuid = rootUuid(rp);
  let cfgDir = null;
  let binPath = null;
  let d = isDir(rp) ? rp : dirname(rp);
  for (let i = 0; i < 12 && d; i++) {
    if (isExternalObjectRoot(d + '.xml')) return allow();
    if (!elemUuid) elemUuid = rootUuid(d + '.xml');
    if (!cfgDir) {
      const cand = join(d, 'Ext', 'ParentConfigurations.bin');
      if (existsSync(cand) || existsSync(join(d, 'Configuration.xml'))) { cfgDir = d; binPath = cand; }
    }
    if (elemUuid && cfgDir) break;
    const parent = dirname(d);
    if (parent === d) break;
    d = parent;
  }
  if (!cfgDir || !inDumpScope(cfgDir, rp)) return allow({ cfgDir });
  // New object (no element file yet): the configuration root decides.
  if (!elemUuid) elemUuid = rootUuid(join(cfgDir, 'Configuration.xml'));
  if (!existsSync(binPath)) return allow({ cfgDir });

  let G = 0, K = 0, text = null, parsed = false;
  try {
    let data = readFileSync(binPath);
    if (data.length > 32) {
      if (data[0] === 0xef && data[1] === 0xbb && data[2] === 0xbf) data = data.subarray(3);
      text = data.toString('utf8');
      const h = /^\{6,(\d+),(\d+),/.exec(text);
      if (h) { G = parseInt(h[1], 10); K = parseInt(h[2], 10); parsed = true; }
    }
  } catch { parsed = false; }
  if (!parsed) {
    return { status: 'unknown', code: 'unreadable', cfgDir, binPath,
      reason: `файл состояния поддержки «${binPath}» существует, но не читается или не разбирается — состояние объекта неизвестно, он может быть на замке` };
  }
  if (K === 0) return allow({ cfgDir, binPath });

  let best = null;
  if (elemUuid) {
    const re = new RegExp('([0-2]),0,' + elemUuid.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
    let m;
    while ((m = re.exec(text)) !== null) {
      const f1 = parseInt(m[1], 10);
      if (best === null || f1 < best) best = f1;
    }
  }
  const blocked = (code, reason) => ({ status: 'blocked', code, reason, cfgDir, binPath });
  if (G === 1) return blocked('capability-off', 'возможность изменения конфигурации выключена (вся конфигурация read-only)');
  if (require === 'removed') {
    if (best !== null && best !== 2) return blocked('not-removed', 'объект не снят с поддержки — удаление сломает обновления');
  } else if (best === 0) {
    return blocked('locked', 'объект на замке — редактирование сломает обновления');
  }
  return allow({ cfgDir, binPath });
}

// ---------------------------------------------------------------- decision

function diagnostic(r, target) {
  const head = '[support-guard] Редактирование отклонено: это объект типовой конфигурации на поддержке поставщика, прямое редактирование молча сломает будущие обновления.';
  const cfe = 'Рекомендуемый путь: внести доработку в расширение (cfe-borrow / cfe-patch-method) — состояние поддержки менять не нужно, обновления вендора сохраняются.';
  const noBypass = 'Не обходите отказ записью файла через Bash или PowerShell: это та же прямая правка.';
  const off = 'Снять проверку: SUPPORT_GUARD = warn|off в .dev.env (её же читают инструменты 1c-metadata-manage); выключить только этот хук — SUPPORT_GUARD_HOOK. Канон — docs/support-manage.md скилла 1c-metadata-manage.';
  let state, fix;
  if (r.code === 'unreadable') {
    state = `Состояние: ${r.reason}.`;
    fix = 'Проверьте целостность выгрузки (Ext/ParentConfigurations.bin).';
  } else if (r.code === 'capability-off') {
    state = `Состояние: у всей конфигурации выключена возможность изменения (режим read-only «из коробки») — поэтому «${target}» редактировать нельзя.`;
    fix = `Либо снять защиту явно (support-edit, два шага):\n  1. support-edit -Path "${r.cfgDir}" -Capability on — включить возможность изменения (объекты пока остаются на замке);\n  2. support-edit -Path "${target}" -Set editable — открыть этот объект.\n  Изменение применяется в базу полной загрузкой выгрузки и обходит механизм обновлений вендора.`;
  } else {
    state = `Состояние: объект «${target}» на замке (возможность изменения конфигурации включена, но сам объект не редактируется).`;
    fix = `Либо разрешить редактирование этого объекта (support-edit, выбрать одно):\n  support-edit -Path "${target}" -Set editable — редактировать и дальше получать обновления вендора (возможны конфликты слияния);\n  support-edit -Path "${target}" -Set off-support — снять с поддержки: обновления по объекту больше не приходят.`;
  }
  return [head, state, cfe, fix, noBypass, off].join('\n');
}

function candidatePaths(toolInput) {
  const out = [];
  if (!toolInput || typeof toolInput !== 'object') return out;
  if (typeof toolInput.file_path === 'string') out.push(toolInput.file_path);
  if (Array.isArray(toolInput.file_edits)) {
    for (const e of toolInput.file_edits) if (e && typeof e.file_path === 'string') out.push(e.file_path);
  }
  return out;
}

// Pure decision: returns the stdout text ('' = allow silently). Never throws.
export function processInput(input, env = process.env) {
  try {
    const major = parseInt(String(process.versions.node).split('.')[0], 10);
    if (major < 18) {
      return JSON.stringify({ systemMessage: `${NOTICE} нужен Node 18+, найден ${process.versions.node} — хук пропущен, правка разрешена.` });
    }
    const cwd = typeof input?.cwd === 'string' && input.cwd ? input.cwd : (env.CLAUDE_PROJECT_DIR || process.cwd());
    const envFile = findDevEnvFile(cwd);
    if (!hookEnabled(envFile)) return '';
    const mode = guardMode(envFile);
    if (mode === 'off') return '';
    for (const p of candidatePaths(input?.tool_input)) {
      const target = isAbsolute(p) ? resolve(p) : resolve(cwd, p);
      const r = decideSupport(target, 'editable');
      if (r.status === 'allow') continue;
      if (mode === 'warn') {
        return JSON.stringify({ systemMessage: `${NOTICE} ПРЕДУПРЕЖДЕНИЕ (SUPPORT_GUARD=warn): ${r.reason}. Цель: ${target}` });
      }
      return JSON.stringify({
        hookSpecificOutput: {
          hookEventName: 'PreToolUse',
          permissionDecision: 'deny',
          permissionDecisionReason: diagnostic(r, target),
        },
      });
    }
    return '';
  } catch (e) {
    return JSON.stringify({ systemMessage: `${NOTICE} проверка не выполнена (${String(e && e.message || e).split('\n')[0]}) — правка разрешена.` });
  }
}

async function readStdin() {
  const chunks = [];
  for await (const c of process.stdin) chunks.push(c);
  return Buffer.concat(chunks).toString('utf8');
}

function isMain() {
  if (!process.argv[1]) return false;
  const self = fileURLToPath(import.meta.url);
  const arg = resolve(process.argv[1]);
  return WIN ? self.toLowerCase() === arg.toLowerCase() : self === arg;
}

if (isMain()) {
  let out = '';
  try {
    const raw = await readStdin();
    let input = {};
    const text = raw.replace(/^\uFEFF/, '');
    try { input = text.trim() ? JSON.parse(text) : {}; } catch { input = {}; }
    out = processInput(input);
  } catch (e) {
    out = JSON.stringify({ systemMessage: `${NOTICE} проверка не выполнена (${String(e && e.message || e).split('\n')[0]}) — правка разрешена.` });
  }
  if (out) process.stdout.write(out + '\n');
  process.exit(0);
}
