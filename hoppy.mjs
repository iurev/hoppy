#!/usr/bin/env node

import { $, argv } from 'zx';
import { createRequire } from 'module';
import fs from 'fs';
import os from 'os';
import path from 'path';
import process from 'process';
import { fileURLToPath } from 'url';
import { LocalStorage } from 'node-localstorage';
import { spawn } from 'child_process';

const require = createRequire(import.meta.url);
const Frecency = require('@getstation/frecency');

// Inspired by /home/yu/.tmux/plugins/tmux-fzf/scripts/session.sh

$.verbose = false;

const scriptFilePath = fileURLToPath(import.meta.url);
const scriptDir = path.dirname(scriptFilePath);
const logFilePath = path.join(scriptDir, 'hoppy.log');
const LOG_MAX_BYTES = 256 * 1024;
const LOG_TRIM_TARGET = Math.floor(LOG_MAX_BYTES * 0.8);
const fsp = fs.promises;
const SESSION_SWITCH_DEBOUNCE_MS = parseInt(process.env.SESSION_SWITCH_DEBOUNCE_MS, 10) || 300;
const sessionDebounceFile = path.join('/tmp', `tmux-session-${getTmpUserId()}.json`);

// Initialize frecency
const frecencyStorageDir = path.join(scriptDir, '.hoppy-frecency');
const frecencyStorage = new LocalStorage(frecencyStorageDir);
const sessionFrecency = new Frecency({
  key: 'tmux-sessions',
  storageProvider: frecencyStorage,
});

await sourceEnv();
await ensureEnvDefaults();

const baseFzfDefaultOpts = process.env.FZF_DEFAULT_OPTS ?? '';
await logEvent('script started');

const currentSession = await getCurrentSession();
await logEvent(`current session: ${currentSession}`);

const excludeCurrent = !process.env.TMUX_FZF_SWITCH_CURRENT;
await logEvent(`exclude current from list: ${excludeCurrent}`);

let action = argv._[0] ? String(argv._[0]) : await selectAction();
await logEvent(`action selected: ${action}`);

if (!action || action === '[cancel]') {
  await logEvent('action cancelled or empty, exiting');
  process.exit(0);
}

// Handle popup action - creates a popup and runs switch inside it
if (action === 'popup-switch') {
  await logEvent('action=popup-switch: creating popup for session switching');
  const scriptPath = fileURLToPath(import.meta.url);
  await $`tmux display-popup -E -w 60% -h 90% -x R -y C -T "SESSIONS" -b rounded ${scriptPath} switch`;
  await logEvent('action=popup-switch: complete');
  process.exit(0);
}

// Handle popup-worktree-switch action - creates a popup and runs worktree-switch inside it
if (action === 'popup-worktree-switch') {
  await logEvent('action=popup-worktree-switch: creating popup for worktree session switching');
  const scriptPath = fileURLToPath(import.meta.url);
  await $`tmux display-popup -E -w 60% -h 90% -x R -y C -T "WORKTREE SESSIONS" -b rounded ${scriptPath} worktree-switch`;
  await logEvent('action=popup-worktree-switch: complete');
  process.exit(0);
}

// Handle popup-capital-switch action - creates a popup and runs capital-switch inside it
if (action === 'popup-capital-switch') {
  await logEvent('action=popup-capital-switch: creating popup for capital session switching');
  const scriptPath = fileURLToPath(import.meta.url);
  await $`tmux display-popup -E -w 60% -h 90% -x R -y C -T "CAPITAL SESSIONS" -b rounded ${scriptPath} capital-switch`;
  await logEvent('action=popup-capital-switch: complete');
  process.exit(0);
}

// Handle helper actions for fzf bindings
if (action === 'reload-sessions') {
  await logEvent('action=reload-sessions: fetching sessions for fzf reload');
  const sessions = await getSessionsList({ currentSession: null, excludeCurrent: false });
  await logEvent(`action=reload-sessions: outputting ${sessions.length} sessions`);

  // Apply number prefixes to match the main list
  const numberedSessions = addNumberPrefixes(sessions);
  console.log(numberedSessions.join('\n'));
  process.exit(0);
}

if (action === 'kill-single-from-line') {
  const selectedLine = argv._[1] ? String(argv._[1]) : '';
  const sessionName = extractSessionName(selectedLine);
  await logEvent(`action=kill-single-from-line: extracted session: ${sessionName}`);

  if (sessionName) {
    try {
      await $`tmux kill-session -t ${sessionName}`;
      await logEvent(`action=kill-single-from-line: killed ${sessionName}`);
    } catch (error) {
      await logEvent(`action=kill-single-from-line: failed to kill ${sessionName}`);
    }
}
  process.exit(0);
}

if (action === 'delayed-switch') {
  const token = argv._[1] ? String(argv._[1]) : '';
  await logEvent(`action=delayed-switch: token=${token || '(empty)'}`);
  await handleDelayedSwitch(token);
  process.exit(0);
}

if (action === 'switch-from-line') {
  const selectedLine = argv._[1] ? String(argv._[1]) : '';
  const sessionName = extractSessionName(selectedLine);
  await logEvent(`action=switch-from-line: extracted session: ${sessionName}`);

  if (!sessionName || sessionName === '[cancel]') {
    await logEvent('action=switch-from-line: no session to process');
    process.exit(0);
  }

  try {
    const result = await scheduleSessionSwitch(sessionName);
    if (result.switchedImmediately) {
      await logEvent(`action=switch-from-line: switched immediately to ${sessionName}`);
    } else if (result.scheduled) {
      await logEvent(`action=switch-from-line: scheduled switch for ${sessionName}`);
    } else {
      await logEvent(`action=switch-from-line: no switch scheduled for ${sessionName}`);
    }
  } catch (error) {
    await logEvent(`action=switch-from-line: failed to switch to ${sessionName}: ${error?.message}`);
  }
  process.exit(0);
}

// DEFENSIVE: Validate action before proceeding
try {
  assertValidAction(action);
} catch (error) {
  await logEvent(`Invalid action: ${error.message}`);
  console.error(`Error: ${error.message}`);
  process.exit(1);
}

// Handle kill-single action (triggered by DEL key in fzf)
if (action === 'kill-single') {
  await logEvent('action=kill-single: processing single session kill');

  // DEFENSIVE: Validate argument provided
  if (!argv._[1]) {
    await logEvent('action=kill-single: no session name provided');
    console.error('Error: Session name required for kill-single action');
    process.exit(1);
  }

  const sessionName = String(argv._[1]);
  await logEvent(`action=kill-single: session name: ${sessionName}`);

  // DEFENSIVE: Validate session name
  try {
    assertValidSessionName(sessionName);
  } catch (error) {
    await logEvent(`action=kill-single: Invalid session name: ${error.message}`);
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }

  // DEFENSIVE: Check if session exists
  try {
    await $`tmux has-session -t ${sessionName}`;
    await logEvent(`action=kill-single: session ${sessionName} exists`);
  } catch (error) {
    await logEvent(`action=kill-single: session ${sessionName} does not exist`);
    await $`tmux display-message "Session ${sessionName} does not exist"`;
    process.exit(1);
  }

  // Show confirmation and kill if confirmed
  await logEvent(`action=kill-single: showing confirmation for ${sessionName}`);

  // Simple text-based confirmation prompt
  // This will be shown by fzf's execute action (not execute-silent)
  console.log(`\n⚠️  Kill session "${sessionName}"?`);
  console.log('Press Y to confirm, any other key to cancel...\n');

  // Read a single character from stdin with timeout and error handling
  let answer = '';
  try {
    answer = await Promise.race([
      new Promise((resolve) => {
        process.stdin.setRawMode(true);
        process.stdin.resume();
        process.stdin.once('data', (key) => {
          try {
            process.stdin.setRawMode(false);
            process.stdin.pause();
          } catch (e) {
            // Ignore cleanup errors
          }
          resolve(key.toString());
        });
      }),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Timeout')), 30000)
      )
    ]);
  } catch (error) {
    await logEvent(`action=kill-single: stdin read failed: ${error?.message}`);
    console.log('✗ Timeout or error, kill cancelled');
    try {
      process.stdin.setRawMode(false);
      process.stdin.pause();
    } catch (e) {
      // Ignore cleanup errors
    }
    process.exit(0);
  }

  // DEFENSIVE: Validate answer is a string
  if (typeof answer !== 'string') {
    await logEvent(`action=kill-single: invalid answer type: ${typeof answer}`);
    console.log('✗ Invalid input, kill cancelled');
    process.exit(0);
  }

  await logEvent(`action=kill-single: user answered: ${answer}`);

  if (answer.match(/^[Yy]$/)) {
    await logEvent(`action=kill-single: killing session ${sessionName}`);
    try {
      await $`tmux kill-session -t ${sessionName}`;
      console.log(`✓ Session "${sessionName}" killed`);
      await logEvent(`action=kill-single: session ${sessionName} killed successfully`);
    } catch (error) {
      console.log(`✗ Failed to kill session "${sessionName}"`);
      await logEvent(`action=kill-single: failed to kill session: ${error?.message}`);
    }
  } else {
    console.log('✗ Kill cancelled');
    await logEvent(`action=kill-single: kill cancelled by user`);
  }

  // Brief pause so user can see the result
  await new Promise(resolve => setTimeout(resolve, 800));

  await logEvent('action=kill-single: complete');
  process.exit(0);
}

await logEvent(`action=${action}`);

if (action === 'new') {
  await logEvent('action=new: prompting for session name');
  const sessionName = await promptSessionName();
  await logEvent(`action=new: session name entered: ${sessionName}`);
  if (!sessionName) {
    await logEvent('action=new: no session name provided, exiting');
    process.exit(0);
  }

  // DEFENSIVE: Validate session name before creating
  try {
    assertValidSessionName(sessionName);
  } catch (error) {
    await logEvent(`Invalid session name: ${error.message}`);
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }

  await logEvent(`action=new: creating new session: ${sessionName}`);
  await $`tmux new-session -d -s ${sessionName}`;
  await logEvent(`action=new: switching to session: ${sessionName}`);
  try {
    await $`tmux switch-client -t ${sessionName}`;
    await logEvent('action=new: complete');
  } catch (error) {
    await logEvent(`action=new: switch-client failed: ${error.message}`);
    process.exit(1);
  }
  process.exit(0);
}

// Handle worktree-switch action - shows only sessions related to git worktrees
if (action === 'worktree-switch') {
  await logEvent('action=worktree-switch: starting');

  // Step 1: Get current pane path
  const { stdout: panePathRaw } = await $`tmux display-message -p '#{pane_current_path}'`;
  const currentPath = panePathRaw.trim();
  await logEvent(`action=worktree-switch: current pane path: ${currentPath}`);

  // Step 2: Get git worktrees for current path
  const worktreePaths = await getGitWorktrees(currentPath);
  if (worktreePaths.length === 0) {
    await logEvent('action=worktree-switch: no git repo/worktrees found');
    await $`tmux display-message "Not in a git repository"`;
    process.exit(0);
  }
  await logEvent(`action=worktree-switch: worktrees: ${worktreePaths.join(', ')}`);

  // Step 3: Get all pane paths (single tmux call)
  const allPanePaths = await getAllPanePaths();

  // Step 4: Get all sessions
  const allSessions = await getSessionsList({ currentSession, excludeCurrent: false });
  await logEvent(`action=worktree-switch: total sessions: ${allSessions.length}`);

  // Step 5: Filter sessions by worktree paths
  const filteredSessions = filterSessionsByWorktrees(allSessions, worktreePaths, allPanePaths);
  await logEvent(`action=worktree-switch: filtered sessions: ${filteredSessions.length}`);

  if (filteredSessions.length === 0) {
    await $`tmux display-message "No sessions found for this project's worktrees"`;
    process.exit(0);
  }

  // Step 6: Build fzf bindings
  const scriptPath = fileURLToPath(import.meta.url);

  // TODO: DEL binding not supported for worktree view yet (would need reload-worktree-sessions action)
  // const delBinding = `--bind 'del:...'`;

  const ctrlNBinding = `--bind 'ctrl-n:down+execute-silent(${scriptPath} switch-from-line {})'`;
  const ctrlPBinding = `--bind 'ctrl-p:up+execute-silent(${scriptPath} switch-from-line {})'`;
  const previewBindings = `${ctrlNBinding} ${ctrlPBinding}`;

  // Step 7: Show fzf picker
  const selection = await selectSessions({
    sessions: filteredSessions,
    includeCurrent: false,
    currentSession,
    header: `Worktree sessions (${filteredSessions.length}/${allSessions.length}). Ctrl+N/P to preview.`,
    includePreview: true,
    extraBindings: previewBindings,
  });
  await logEvent(`action=worktree-switch: selection: ${selection}`);

  // Step 8: Parse and switch
  const targets = parseTargets(selection, currentSession);
  if (targets.length === 0) {
    await logEvent('action=worktree-switch: no target selected');
    process.exit(0);
  }

  // Validate target
  try {
    assertValidSessionName(targets[0]);
  } catch (error) {
    await logEvent(`action=worktree-switch: invalid target: ${error.message}`);
    process.exit(1);
  }

  await logEvent(`action=worktree-switch: switching to ${targets[0]}`);
  await $`tmux switch-client -t ${targets[0]}`;

  // Record frecency
  sessionFrecency.save({ selectedId: targets[0] });
  await logEvent(`action=worktree-switch: recorded frecency for ${targets[0]}`);

  await logEvent('action=worktree-switch: complete');
  process.exit(0);
}

// Handle capital-switch action - shows only sessions with CAPITAL letter names
if (action === 'capital-switch') {
  await logEvent('action=capital-switch: starting');

  // Get all sessions
  const allSessions = await getSessionsList({ currentSession, excludeCurrent: false });
  await logEvent(`action=capital-switch: total sessions: ${allSessions.length}`);

  // Filter sessions to only those with ALL CAPITAL letters (allowing numbers, underscores, hyphens)
  const capitalSessions = allSessions.filter(sessionLine => {
    const sessionName = extractSessionName(sessionLine);
    // Match names that are all uppercase (no lowercase letters)
    return /^[A-Z0-9_\-\s]+$/.test(sessionName) && /[A-Z]/.test(sessionName);
  });
  await logEvent(`action=capital-switch: capital sessions: ${capitalSessions.length}`);

  if (capitalSessions.length === 0) {
    await $`tmux display-message "No CAPITAL sessions found"`;
    process.exit(0);
  }

  // Build fzf bindings
  const scriptPath = fileURLToPath(import.meta.url);

  const ctrlNBinding = `--bind 'ctrl-n:down+execute-silent(${scriptPath} switch-from-line {})'`;
  const ctrlPBinding = `--bind 'ctrl-p:up+execute-silent(${scriptPath} switch-from-line {})'`;
  const previewBindings = `${ctrlNBinding} ${ctrlPBinding}`;

  // Show fzf picker
  const selection = await selectSessions({
    sessions: capitalSessions,
    includeCurrent: false,
    currentSession,
    header: `CAPITAL sessions (${capitalSessions.length}/${allSessions.length}). Ctrl+N/P to preview.`,
    includePreview: true,
    extraBindings: previewBindings,
  });
  await logEvent(`action=capital-switch: selection: ${selection}`);

  // Parse and switch
  const targets = parseTargets(selection, currentSession);
  if (targets.length === 0) {
    await logEvent('action=capital-switch: no target selected');
    process.exit(0);
  }

  // Validate target
  try {
    assertValidSessionName(targets[0]);
  } catch (error) {
    await logEvent(`action=capital-switch: invalid target: ${error.message}`);
    process.exit(1);
  }

  await logEvent(`action=capital-switch: switching to ${targets[0]}`);
  await $`tmux switch-client -t ${targets[0]}`;

  // Record frecency
  sessionFrecency.save({ selectedId: targets[0] });
  await logEvent(`action=capital-switch: recorded frecency for ${targets[0]}`);

  await logEvent('action=capital-switch: complete');
  process.exit(0);
}

const sessions = await getSessionsList({ currentSession, excludeCurrent: false });
await logEvent(`sessions list retrieved: ${sessions.length} sessions`);

if (action === 'switch') {
  await logEvent('action=switch: showing session selector');

  // Build the DEL key binding for killing sessions
  const scriptPath = fileURLToPath(import.meta.url);
  const format = process.env.TMUX_FZF_SESSION_FORMAT;

  // DEFENSIVE: Validate script path
  if (!scriptPath || typeof scriptPath !== 'string') {
    throw new Error('Could not determine script path');
  }
  if (scriptPath.length > 4096) {
    throw new Error('Script path is too long');
  }
  // Check for shell metacharacters in script path (should not happen, but be safe)
  if (/[`$;|&<>(){}[\]!\\]/.test(scriptPath)) {
    throw new Error('Script path contains unsafe characters');
  }

  // DEFENSIVE: Validate format string if present
  if (format) {
    if (typeof format !== 'string') {
      throw new Error('TMUX_FZF_SESSION_FORMAT must be a string');
    }
    if (format.length > 500) {
      throw new Error('TMUX_FZF_SESSION_FORMAT exceeds max length');
    }
    // Check for command injection attempts in format string
    if (/[`$;|&<>()]/.test(format)) {
      throw new Error('TMUX_FZF_SESSION_FORMAT contains unsafe characters');
    }
  }

  // Helper function to extract session name from fzf line
  function extractSessionNameFromLine(line) {
    // After column -t, the session name is the first whitespace-separated field
    return line.split(/\s+/)[0];
  }

  // Build fzf bindings by calling this script with different actions
  // fzf will pass the selected line as an argument
  const delBinding = `--bind 'del:execute(${scriptPath} kill-single-from-line {})+reload(${scriptPath} reload-sessions)'`;
  const ctrlNBinding = `--bind 'ctrl-n:down+execute-silent(${scriptPath} switch-from-line {})'`;
  const ctrlPBinding = `--bind 'ctrl-p:up+execute-silent(${scriptPath} switch-from-line {})'`;
  const switchBinding = `${ctrlNBinding} ${ctrlPBinding}`;

  // Build number key bindings (1-9) for quick session switching
  const numberBindings = [
    '1:pos(1)+accept',
    '2:pos(2)+accept',
    '3:pos(3)+accept',
    '4:pos(4)+accept',
    '5:pos(5)+accept',
    '6:pos(6)+accept',
    '7:pos(7)+accept',
    '8:pos(8)+accept',
    '9:pos(9)+accept'
  ].join(',');
  const numberBinding = `--bind '${numberBindings}'`;

  await logEvent(`action=switch: DEL binding: ${delBinding}`);

  const selection = await selectSessions({
    sessions,
    includeCurrent: false,
    currentSession,
    header: 'Select target session. Press 1-9 for quick switch. DEL to kill. Ctrl+N/P to preview.',
    includePreview: true,
    extraBindings: `${delBinding} ${switchBinding} ${numberBinding}`,
  });
  await logEvent(`action=switch: selection made: ${selection}`);
  const targets = parseTargets(selection, currentSession);
  await logEvent(`action=switch: parsed targets: ${JSON.stringify(targets)}`);
  if (targets.length === 0) {
    await logEvent('action=switch: no targets selected, exiting');
    process.exit(0);
  }

  // DEFENSIVE: Validate target session name
  try {
    assertValidSessionName(targets[0]);
  } catch (error) {
    await logEvent(`Invalid target session: ${error.message}`);
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }

  await logEvent(`action=switch: switching to ${targets[0]}`);
  try {
    await $`tmux switch-client -t ${targets[0]}`;
    // Record the switch in frecency
    sessionFrecency.save({ selectedId: targets[0] });
    await logEvent(`action=switch: recorded frecency for ${targets[0]}`);
    await logEvent('action=switch: complete');
  } catch (error) {
    await logEvent(`action=switch: switch-client failed: ${error.message}`);
    if (error.stderr) await logEvent(`action=switch: stderr: ${error.stderr}`);
    if (error.stdout) await logEvent(`action=switch: stdout: ${error.stdout}`);
    process.exit(1);
  }
  process.exit(0);
}

if (action === 'rename') {
  await logEvent('action=rename: prompting for new session name');
  const sessionName = await promptSessionName();
  await logEvent(`action=rename: new session name entered: ${sessionName}`);
  if (!sessionName) {
    await logEvent('action=rename: no session name provided, exiting');
    process.exit(0);
  }

  // DEFENSIVE: Validate new session name
  try {
    assertValidSessionName(sessionName);
  } catch (error) {
    await logEvent(`Invalid new session name: ${error.message}`);
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }

  await logEvent('action=rename: showing session selector');
  const selection = await selectSessions({
    sessions,
    includeCurrent: true,
    header: 'Select target session.',
    includePreview: true,
  });
  await logEvent(`action=rename: selection made: ${selection}`);
  const targets = parseTargets(selection, currentSession);
  await logEvent(`action=rename: parsed targets: ${JSON.stringify(targets)}`);
  if (targets.length === 0) {
    await logEvent('action=rename: no targets selected, exiting');
    process.exit(0);
  }

  // DEFENSIVE: Validate target session name
  try {
    assertValidSessionName(targets[0]);
  } catch (error) {
    await logEvent(`Invalid target session: ${error.message}`);
    console.error(`Error: ${error.message}`);
    process.exit(1);
  }

  await logEvent(`action=rename: renaming ${targets[0]} to ${sessionName}`);
  await $`tmux rename-session -t ${targets[0]} ${sessionName}`;
  await logEvent('action=rename: complete');
  process.exit(0);
}

if (action === 'kill') {
  await logEvent('action=kill: showing session selector');
  const selection = await selectSessions({
    sessions,
    includeCurrent: true,
    header: 'Select target session(s). Press TAB to mark multiple items.',
    includePreview: true,
  });
  await logEvent(`action=kill: selection made: ${selection}`);
  const targets = parseTargets(selection, currentSession);
  await logEvent(`action=kill: parsed targets: ${JSON.stringify(targets)}`);
  if (targets.length === 0) {
    await logEvent('action=kill: no targets selected, exiting');
    process.exit(0);
  }

  // DEFENSIVE: Validate all target session names
  for (const target of targets) {
    try {
      assertValidSessionName(target);
    } catch (error) {
      await logEvent(`Invalid target session: ${error.message}`);
      console.error(`Error: ${error.message}`);
      process.exit(1);
    }
  }

  const ordered = targets.slice().sort().reverse();
  await logEvent(`action=kill: ordered targets for killing: ${JSON.stringify(ordered)}`);
  for (const target of ordered) {
    await logEvent(`action=kill: killing session ${target}`);
    await $`tmux kill-session -t ${target}`;
  }
  await logEvent('action=kill: complete');
  process.exit(0);
}

if (action === 'detach') {
  await logEvent('action=detach: showing session selector');
  const selection = await selectDetachSessions({
    sessions,
    currentSession,
    header: 'Select target session(s). Press TAB to mark multiple items.',
  });
  await logEvent(`action=detach: selection made: ${selection}`);
  const targets = parseTargets(selection, currentSession);
  await logEvent(`action=detach: parsed targets: ${JSON.stringify(targets)}`);
  if (targets.length === 0) {
    await logEvent('action=detach: no targets selected, exiting');
    process.exit(0);
  }

  // DEFENSIVE: Validate all target session names
  for (const target of targets) {
    try {
      assertValidSessionName(target);
    } catch (error) {
      await logEvent(`Invalid target session: ${error.message}`);
      console.error(`Error: ${error.message}`);
      process.exit(1);
    }
  }

  for (const target of targets) {
    await logEvent(`action=detach: detaching session ${target}`);
    await $`tmux detach -s ${target}`;
  }
  await logEvent('action=detach: complete');
  process.exit(0);
}

await logEvent('script complete, exiting normally');
process.exit(0);

async function selectAction() {
  await logEvent('selectAction: showing action menu');
  const selection = await runFzf([
    'switch',
    'new',
    'rename',
    'detach',
    'kill',
    '[cancel]',
  ], {
    header: 'Select an action.',
    includePreview: false,
  });
  await logEvent(`selectAction: raw selection: ${selection}`);
  const lines = parseLines(selection);
  const result = lines[0] ?? '';
  await logEvent(`selectAction: returning: ${result}`);
  return result;
}

async function selectSessions({ sessions, includeCurrent, currentSession, header, includePreview, extraBindings }) {
  const items = [];

  // Put current session at the top if we have it, but preserve frecency order for the rest
  if (currentSession) {
    const currentLine = sessions.find(line => line.startsWith(`${currentSession} @ `));
    if (currentLine) {
      items.push(currentLine);
      // Add remaining sessions in their frecency-sorted order (excluding current)
      items.push(...sessions.filter(line => line !== currentLine));
    } else {
      // Sessions are already sorted by frecency from getSessionsList
      items.push(...sessions);
    }
  } else {
    if (includeCurrent) {
      items.push('[current]');
    }
    // Sessions are already sorted by frecency from getSessionsList
    items.push(...sessions);
  }

  // Add number prefixes using the shared helper function
  const numberedItems = addNumberPrefixes(items);

  numberedItems.push('[cancel]');
  return runFzf(numberedItems, { header, includePreview, extraBindings });
}

async function selectDetachSessions({ sessions, currentSession, header }) {
  const attachedNames = await getAttachedSessionNames();
  const filtered = sessions.filter((line) => attachedNames.has(extractSessionName(line)));
  const items = ['[current]', ...filtered, '[cancel]'];
  return runFzf(dedupe(items), { header, includePreview: true });
}

// ============================================================================
// Session switch throttling helpers (delayed activation)
// ============================================================================

function getTmpUserId() {
  try {
    const info = os.userInfo();
    if (info && typeof info.uid !== 'undefined') {
      return String(info.uid);
    }
    if (info && typeof info.username === 'string' && info.username.length > 0) {
      return info.username;
    }
  } catch (error) {
    // Fall through to PID fallback
  }
  return `pid-${process.pid}`;
}

async function readSessionDebounceState(filePath) {
  try {
    const raw = await fsp.readFile(filePath, 'utf8');
    const parsed = JSON.parse(raw);
    const lastWrite = Number(parsed?.lastWrite);
    const lastTarget = typeof parsed?.lastTarget === 'string' ? parsed.lastTarget : null;
    const token = typeof parsed?.token === 'string' ? parsed.token : null;
    return {
      lastWrite: Number.isFinite(lastWrite) ? lastWrite : 0,
      lastTarget,
      token,
    };
  } catch (error) {
    if (error?.code === 'ENOENT') {
      return { lastWrite: 0, lastTarget: null, token: null };
    }
    if (error?.code === 'EACCES' || error?.code === 'EPERM') {
      await logEvent(`session debounce: no read access to ${filePath}: ${error.code}`);
      return { lastWrite: 0, lastTarget: null, token: null };
    }
    if (error instanceof SyntaxError) {
      await logEvent(`session debounce: invalid JSON in ${filePath}, resetting`);
      return { lastWrite: 0, lastTarget: null, token: null };
    }
    await logEvent(`session debounce: unexpected read error for ${filePath}: ${error?.message}`);
    return { lastWrite: 0, lastTarget: null, token: null };
  }
}

async function writeSessionDebounceState(filePath, state) {
  const payload = JSON.stringify({
    lastWrite: Number.isFinite(state?.lastWrite) ? state.lastWrite : Date.now(),
    lastTarget: typeof state?.lastTarget === 'string' ? state.lastTarget : null,
    token: typeof state?.token === 'string' ? state.token : null,
  });
  try {
    await fsp.writeFile(filePath, payload, { encoding: 'utf8', mode: 0o600 });
    return true;
  } catch (error) {
    if (error?.code === 'EACCES' || error?.code === 'EPERM') {
      await logEvent(`session debounce: no write access to ${filePath}: ${error.code}`);
      return false;
    }
    await logEvent(`session debounce: failed to write ${filePath}: ${error?.message}`);
    return false;
  }
}

async function scheduleSessionSwitch(targetName) {
  const trimmedName = typeof targetName === 'string' ? targetName.trim() : '';
  if (!trimmedName) {
    return { switchedImmediately: false, scheduled: false };
  }

  const now = Date.now();
  const token = `${now}-${process.pid}-${Math.random().toString(36).slice(2, 10)}`;
  const writeSucceeded = await writeSessionDebounceState(sessionDebounceFile, {
    lastWrite: now,
    lastTarget: trimmedName,
    token,
  });
  await logEvent(
    `session throttle: ${writeSucceeded ? 'scheduled' : 'write failed'} target=${trimmedName} token=${token}`
  );

  if (!writeSucceeded) {
    try {
      await $`tmux switch-client -t ${trimmedName}`;
      await logEvent(`session throttle: immediate fallback switch for ${trimmedName}`);
      await writeSessionDebounceState(sessionDebounceFile, {
        lastWrite: Date.now(),
        lastTarget: trimmedName,
        token: null,
      });
      return { switchedImmediately: true, scheduled: false };
    } catch (error) {
      await logEvent(`session throttle: fallback switch failed for ${trimmedName}: ${error?.message}`);
      return { switchedImmediately: false, scheduled: false };
    }
  }

  try {
    const child = spawn(process.execPath, [scriptFilePath, 'delayed-switch', token], {
      detached: true,
      stdio: 'ignore',
    });
    child.unref();
    return { switchedImmediately: false, scheduled: true };
  } catch (error) {
    await logEvent(`session throttle: spawn failed for ${trimmedName}: ${error?.message}`);
    try {
      await $`tmux switch-client -t ${trimmedName}`;
      await logEvent(`session throttle: immediate fallback after spawn failure for ${trimmedName}`);
      await writeSessionDebounceState(sessionDebounceFile, {
        lastWrite: Date.now(),
        lastTarget: trimmedName,
        token: null,
      });
      return { switchedImmediately: true, scheduled: false };
    } catch (fallbackError) {
      await logEvent(
        `session throttle: fallback switch failed after spawn error for ${trimmedName}: ${fallbackError?.message}`
      );
      return { switchedImmediately: false, scheduled: false };
    }
  }
}

async function handleDelayedSwitch(token) {
  if (!token) {
    await logEvent('session throttle: delayed switch invoked without token, skipping');
    return false;
  }

  await delay(SESSION_SWITCH_DEBOUNCE_MS);

  const state = await readSessionDebounceState(sessionDebounceFile);
  const stateToken = typeof state?.token === 'string' ? state.token : null;
  const stateTarget = typeof state?.lastTarget === 'string' ? state.lastTarget.trim() : '';
  if (!stateTarget || stateToken !== token) {
    await logEvent(
      `session throttle: delayed switch skip token=${token}, stateToken=${stateToken ?? 'null'}, target=${stateTarget || '(none)'}`
    );
    return false;
  }

  try {
    await $`tmux switch-client -t ${stateTarget}`;
    await logEvent(`session throttle: delayed switch executed for ${stateTarget}`);
    await writeSessionDebounceState(sessionDebounceFile, {
      lastWrite: Date.now(),
      lastTarget: stateTarget,
      token: null,
    });
    return true;
  } catch (error) {
    await logEvent(`session throttle: delayed switch failed for ${stateTarget}: ${error?.message}`);
    return false;
  }
}

async function runFzf(items, { header, includePreview, extraBindings }) {
  await logEvent(`runFzf: called with ${items?.length} items, header: ${header}, preview: ${includePreview}`);

  // DEFENSIVE: Validate inputs
  assertValidItemsArray(items, 'fzf items');
  assertValidHeader(header);

  if (!items || items.length === 0) {
    await logEvent('runFzf: no items provided, returning empty');
    return '';
  }
  const env = { ...process.env };
  env.FZF_DEFAULT_OPTS = buildFzfDefaultOpts(header, extraBindings);
  env.TMUX_FZF_RUN = buildFzfRunCommand(includePreview);
  await logEvent(`runFzf: FZF_DEFAULT_OPTS: ${env.FZF_DEFAULT_OPTS}`);
  await logEvent(`runFzf: TMUX_FZF_RUN: ${env.TMUX_FZF_RUN}`);

  // DEFENSIVE: Validate environment variables
  assertValidFzfOptions(env.FZF_DEFAULT_OPTS, 'FZF_DEFAULT_OPTS');
  assertValidFzfOptions(env.TMUX_FZF_RUN, 'TMUX_FZF_RUN');

  if (!env.TMUX_FZF_RUN) {
    await logEvent('runFzf: TMUX_FZF_RUN is empty, throwing error');
    throw new Error('TMUX_FZF_RUN command is empty.');
  }
  const body = ensureTrailingNewline(items.join('\n'));
  const script = `
set -e
cat <<'__TMUX_FZF_INPUT__' | eval "$TMUX_FZF_RUN"
${body}__TMUX_FZF_INPUT__
`;
  await logEvent('runFzf: launching fzf');

  // Use spawn directly to avoid zx template literal parsing issues
  return new Promise((resolve, reject) => {
    const proc = spawn('bash', ['-ls'], {
      env,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', async (code) => {
      await logEvent(`runFzf: process exited with code ${code}`);

      if (code === 0) {
        const result = stdout.trimEnd();
        await logEvent(`runFzf: success, stdout: ${result}`);
        resolve(result);
      } else if (code === 130 || code === 1) {
        const result = stdout.trimEnd();
        await logEvent(`runFzf: handled exit code ${code}, returning: ${result}`);
        resolve(result);
      } else {
        await logEvent(`runFzf: error, exit code ${code}, stderr: ${stderr}`);
        reject(new Error(`bash exited with code ${code}: ${stderr}`));
      }
    });

    proc.on('error', async (error) => {
      await logEvent(`runFzf: spawn error: ${error.message}`);
      reject(error);
    });

    // Write script to stdin
    proc.stdin.write(script);
    proc.stdin.end();
  });
}

function buildFzfDefaultOpts(header, extraBindings) {
  // DEFENSIVE: Validate header
  if (header) {
    assertValidHeader(header);
  }

  // DEFENSIVE: Validate extraBindings
  if (extraBindings) {
    if (typeof extraBindings !== 'string') {
      throw new Error('extraBindings must be a string');
    }
    assertValidFzfOptions(extraBindings, 'extraBindings');
  }

  const parts = [
    baseFzfDefaultOpts,
    '--no-sort',
    '--delimiter=" @ "',
    '--with-nth=1..',
    '--nth=1'
  ];
  if (header) {
    const fixed = header.replace(/"/g, '\"');
    parts.push(`--header="${fixed}"`)

  }
  if (extraBindings) {
    parts.push(extraBindings);
  }
  const result = parts.filter(Boolean).join(' ').trim();

  // DEFENSIVE: Validate result
  assertValidFzfOptions(result, 'Built FZF_DEFAULT_OPTS');

  return result;
}

function buildFzfRunCommand(includePreview) {
  // DEFENSIVE: Validate environment variables
  if (process.env.TMUX_FZF_BIN) {
    assertNonEmptyString(process.env.TMUX_FZF_BIN, 'TMUX_FZF_BIN');
    assertMaxLength(process.env.TMUX_FZF_BIN, 'TMUX_FZF_BIN', 1000);
  }
  if (process.env.TMUX_FZF_OPTIONS) {
    assertValidFzfOptions(process.env.TMUX_FZF_OPTIONS, 'TMUX_FZF_OPTIONS');
  }
  if (process.env.TMUX_FZF_PREVIEW_OPTIONS) {
    assertValidFzfOptions(process.env.TMUX_FZF_PREVIEW_OPTIONS, 'TMUX_FZF_PREVIEW_OPTIONS');
  }

  const parts = [process.env.TMUX_FZF_BIN];
  if (process.env.TMUX_FZF_OPTIONS) {
    parts.push(process.env.TMUX_FZF_OPTIONS);
  }
  if (includePreview && process.env.TMUX_FZF_PREVIEW_OPTIONS) {
    parts.push(process.env.TMUX_FZF_PREVIEW_OPTIONS);
  }
  const result = parts.filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();

  // DEFENSIVE: Validate result
  assertValidFzfOptions(result, 'Built TMUX_FZF_RUN');

  return result;
}

/**
 * Formats lines by trimming whitespace and normalizing delimiters.
 * Unlike `column -t`, this preserves the ' @ ' delimiter which is needed
 * for session name extraction and matching.
 * @param {string[]} lines - Array of lines with '@' delimiters
 * @param {string} delimiter - The delimiter (expected to be '@')
 * @returns {string[]} - Array of formatted lines
 */
function columnFormat(lines, delimiter) {
  if (!lines || lines.length === 0) {
    return [];
  }

  // Simply normalize spacing around the delimiter
  // Input:  "ADC @ 3 windows" or "ADC  @  3 windows"
  // Output: "ADC @ 3 windows"
  return lines.map(line => {
    const parts = line.split(delimiter);
    if (parts.length < 2) {
      return line.trim();
    }
    // Trim each part and rejoin with ' @ '
    return parts.map(p => p.trim()).join(' @ ');
  });
}

async function getSessionsList({ currentSession, excludeCurrent }) {
  await logEvent(`getSessionsList: currentSession=${currentSession}, excludeCurrent=${excludeCurrent}`);

  // DEFENSIVE: Validate currentSession
  if (currentSession) {
    try {
      assertValidSessionName(currentSession);
    } catch (error) {
      await logEvent(`Warning: currentSession is invalid: ${error.message}`);
    }
  }

  const format = process.env.TMUX_FZF_SESSION_FORMAT;
  await logEvent(`getSessionsList: TMUX_FZF_SESSION_FORMAT: ${format || '(not set)'}`);

  // DEFENSIVE: Validate format string
  if (format) {
    if (typeof format !== 'string') {
      throw new Error('TMUX_FZF_SESSION_FORMAT must be a string');
    }
    if (format.length > 500) {
      throw new Error('TMUX_FZF_SESSION_FORMAT exceeds max length of 500 characters');
    }
  }

  // Format: session_name @ window_count (using @ as delimiter for easier parsing)
  const command = await $`tmux list-sessions -F '#S @ #{session_windows} windows'`;
  const rawLines = parseLines(command.stdout);
  await logEvent(`getSessionsList: retrieved ${rawLines.length} sessions`);

  // Format columns in JS instead of using shell pipe to column
  let lines = columnFormat(rawLines, '@');
  await logEvent(`getSessionsList: formatted ${lines.length} lines`);

  // Sort by frecency (custom implementation since library is search-query based)
  const storageData = JSON.parse(frecencyStorage.getItem('frecency_tmux-sessions') || '{"selections":{}}');
  const selections = storageData.selections || {};

  lines = lines.sort((a, b) => {
    const aName = extractSessionName(a);
    const bName = extractSessionName(b);
    const aData = selections[aName];
    const bData = selections[bName];

    // Calculate frecency score: recent selections weighted more
    const calculateScore = (data) => {
      if (!data || !data.selectedAt || data.selectedAt.length === 0) return 0;
      const now = Date.now();
      const timestamps = data.selectedAt;

      // Weight recent selections more heavily
      const score = timestamps.reduce((acc, ts) => {
        const ageMs = now - ts;
        const ageHours = ageMs / (1000 * 60 * 60);

        // Exponential decay: more recent = higher score
        if (ageHours < 1) return acc + 100;
        if (ageHours < 24) return acc + 50;
        if (ageHours < 24 * 7) return acc + 10;
        return acc + 1;
      }, 0);

      return score;
    };

    const aScore = calculateScore(aData);
    const bScore = calculateScore(bData);

    return bScore - aScore; // Descending order
  });

  const topSessions = lines.slice(0, 5).map(extractSessionName).join(', ');
  await logEvent(`getSessionsList: sorted by frecency, top 5: ${topSessions}`);

  if (!excludeCurrent) {
    await logEvent(`getSessionsList: returning all sessions`);
    return lines;
  }
  const filtered = lines.filter((line) => !line.startsWith(`${currentSession} @ `));
  await logEvent(`getSessionsList: filtered to ${filtered.length} sessions (excluded current)`);
  return filtered;
}

async function getAttachedSessionNames() {
  const { stdout } = await $`tmux list-sessions`;
  const lines = parseLines(stdout);
  return new Set(
    lines
      .filter((line) => line.includes('attached'))
      .map((line) => extractSessionName(line)),
  );
}

/**
 * Get all worktree paths for the git repo containing dirPath.
 * @param {string} dirPath - any path inside a git repo or worktree
 * @returns {Promise<string[]>} - array of absolute worktree paths, or empty array if not a git repo
 */
async function getGitWorktrees(dirPath) {
  try {
    const { stdout } = await $`git -C ${dirPath} worktree list --porcelain`;
    const lines = stdout.split('\n');
    const paths = [];

    for (const line of lines) {
      if (line.startsWith('worktree ')) {
        paths.push(line.slice(9)); // Remove 'worktree ' prefix (9 chars)
      }
    }

    await logEvent(`getGitWorktrees: found ${paths.length} worktrees for ${dirPath}`);
    return paths;
  } catch (error) {
    await logEvent(`getGitWorktrees: not a git repo or error: ${error?.message}`);
    return [];
  }
}

/**
 * Get all pane paths grouped by session name in a single tmux call.
 * @returns {Promise<Map<string, Set<string>>>} - session name → set of pane paths
 */
async function getAllPanePaths() {
  const { stdout } = await $`tmux list-panes -a -F '#{session_name}\t#{pane_current_path}'`;
  const lines = stdout.trim().split('\n').filter(Boolean);

  const sessionPaths = new Map();

  for (const line of lines) {
    const tabIndex = line.indexOf('\t');
    if (tabIndex === -1) continue;

    const sessionName = line.slice(0, tabIndex);
    const panePath = line.slice(tabIndex + 1);

    if (!sessionPaths.has(sessionName)) {
      sessionPaths.set(sessionName, new Set());
    }
    sessionPaths.get(sessionName).add(panePath);
  }

  await logEvent(`getAllPanePaths: found ${sessionPaths.size} sessions with panes`);
  return sessionPaths;
}

/**
 * Filter session list to only those with panes in any of the worktree paths.
 * @param {string[]} sessions - from getSessionsList(), format: "sessionName @ N windows"
 * @param {string[]} worktreePaths - from getGitWorktrees()
 * @param {Map<string, Set<string>>} allPanePaths - from getAllPanePaths()
 * @returns {string[]} - filtered sessions in same format
 */
function filterSessionsByWorktrees(sessions, worktreePaths, allPanePaths) {
  // Normalize worktree paths (remove trailing slashes)
  const normalizedWorktrees = worktreePaths.map(p => p.replace(/\/+$/, ''));

  return sessions.filter(sessionLine => {
    const sessionName = extractSessionName(sessionLine);
    const panePaths = allPanePaths.get(sessionName);

    if (!panePaths || panePaths.size === 0) {
      return false;
    }

    // Check if ANY pane path starts with ANY worktree path
    for (const panePath of panePaths) {
      for (const wt of normalizedWorktrees) {
        // Exact match OR panePath is inside worktree directory
        if (panePath === wt || panePath.startsWith(wt + '/')) {
          return true;
        }
      }
    }

    return false;
  });
}

function parseTargets(selection, currentSession) {
  const lines = parseLines(selection);
  if (lines.length === 0 || lines.includes('[cancel]')) {
    return [];
  }
  return lines
    .map((line) => line.replace('[current]', `${currentSession} @ `))
    .map((line) => extractSessionName(line))
    .filter(Boolean);
}

/**
 * Adds number prefixes [1] through [9] to the first 9 non-special items.
 * Special items (starting with '[') are not numbered.
 * @param {string[]} items - Array of session lines
 * @returns {string[]} - Array with number prefixes added
 */
function addNumberPrefixes(items) {
  const numberedItems = [];
  let numberIndex = 1;

  for (const item of items) {
    // Skip numbering special items like [current]
    if (item.startsWith('[')) {
      numberedItems.push(item);
    } else if (numberIndex <= 9) {
      numberedItems.push(`[${numberIndex}] ${item}`);
      numberIndex++;
    } else {
      numberedItems.push(item);
    }
  }

  return numberedItems;
}

function extractSessionName(line) {
  // Remove number prefix if present: "[1] session @ ..." -> "session @ ..."
  let cleaned = line;
  if (/^\[\d+\] /.test(line)) {
    cleaned = line.replace(/^\[\d+\] /, '');
  }

  const index = cleaned.indexOf(' @ ');
  return index === -1 ? cleaned : cleaned.slice(0, index);
}

function parseLines(text) {
  if (!text) {
    return [];
  }
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

function ensureTrailingNewline(text) {
  return text.endsWith('\n') ? text : `${text}\n`;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, Number(ms) || 0));
}

function dedupe(items) {
  const seen = new Set();
  const result = [];
  for (const item of items) {
    if (!seen.has(item)) {
      seen.add(item);
      result.push(item);
    }
  }
  return result;
}

async function promptSessionName() {
  const tmpDir = os.tmpdir();
  const fifo = path.join(tmpDir, 'tmux_fzf_session_name');

  // DEFENSIVE: Validate fifo path
  if (!tmpDir || typeof tmpDir !== 'string') {
    throw new Error('Could not determine temp directory');
  }
  if (fifo.length > 4096) {
    throw new Error('FIFO path is too long');
  }
  // Ensure path doesn't escape tmpdir
  if (!fifo.startsWith(tmpDir)) {
    throw new Error('FIFO path validation failed');
  }

  await logEvent(`promptSessionName: using fifo at ${fifo}`);
  await $`rm -f ${fifo}`;
  await $`mkfifo ${fifo}`;
  const promptCommand = `tmux split-window -v -l 30% -b "bash -c 'printf \"Session Name: \" && read session_name && echo \"$session_name\" > ${fifo}'"`;
  await logEvent('promptSessionName: opening tmux split-window for input');
  $`bash -lc ${promptCommand}`;
  try {
    await logEvent('promptSessionName: reading from fifo');
    const { stdout } = await $`cat ${fifo}`;
    const result = stdout.trim();
    await logEvent(`promptSessionName: received: ${result}`);
    return result;
  } catch (error) {
    await logEvent(`promptSessionName: error reading fifo: ${error?.message}`);
    if (error?.stdout) {
      const result = String(error.stdout).trim();
      await logEvent(`promptSessionName: returning error stdout: ${result}`);
      return result;
    }
    await logEvent('promptSessionName: returning empty string');
    return '';
  } finally {
    await $`rm -f ${fifo}`;
    await logEvent('promptSessionName: cleaned up fifo');
  }
}

async function getCurrentSession() {
  const { stdout } = await $`tmux display-message -p '#S'`;
  const sessionName = stdout.trim();

  // DEFENSIVE: Validate current session name
  try {
    assertValidSessionName(sessionName);
  } catch (error) {
    await logEvent(`Warning: Current session name is invalid: ${error.message}`);
    // Don't fail here, just log - we got this from tmux itself
  }

  return sessionName;
}

async function sourceEnv() {
  const candidates = [
    path.join(scriptDir, '.envs'),
    path.join(os.homedir(), '.tmux', 'plugins', 'tmux-fzf', 'scripts', '.envs'),
  ];
  await logEvent(`sourceEnv: checking ${candidates.length} candidate paths`);
  for (const candidate of candidates) {
    await logEvent(`sourceEnv: checking ${candidate}`);
    if (!fs.existsSync(candidate)) {
      await logEvent(`sourceEnv: ${candidate} does not exist`);
      continue;
    }

    await logEvent(`sourceEnv: found ${candidate}, sourcing`);
    const quoted = candidate.replace(/"/g, '\\"');
    const script = `source "${quoted}" >/dev/null 2>&1 && env`;
    const { stdout } = await $`bash -lc ${script}`;
    const envMap = parseEnvOutput(stdout);
    await logEvent(`sourceEnv: parsed ${Object.keys(envMap).length} environment variables`);
    Object.entries(envMap).forEach(([key, value]) => {
      process.env[key] = value;
    });
    await logEvent('sourceEnv: environment variables applied');
    return;
  }
  await logEvent('sourceEnv: no .envs file found');
}

function parseEnvOutput(output) {
  const envMap = {};
  for (const line of output.split('\n')) {
    if (!line) {
      continue;
    }
    const idx = line.indexOf('=');
    if (idx === -1) {
      continue;
    }
    const key = line.slice(0, idx);
    const value = line.slice(idx + 1);
    envMap[key] = value;
  }
  return envMap;
}

async function ensureEnvDefaults() {
  if (!process.env.TMUX_FZF_BIN) {
    process.env.TMUX_FZF_BIN = 'fzf';
  }
  if (!process.env.TMUX_FZF_OPTIONS) {
    process.env.TMUX_FZF_OPTIONS = '';
  }
  if (!process.env.TMUX_FZF_PREVIEW_OPTIONS) {
    const kaomoji = await pickPreviewKaomoji();
    process.env.KAOMOJI_PREVIEW_TEXT = kaomoji;
    // process.env.TMUX_FZF_PREVIEW_OPTIONS = [
    //   '--preview \'node -e "process.stdout.write((process.env.KAOMOJI_PREVIEW_TEXT || \\"(^_^)\\") + \\"\\n\\");"\'',
    //   '--preview-window=left:40%'
    // ].join(' ');
  }
  if (!process.env.FZF_DEFAULT_OPTS) {
    process.env.FZF_DEFAULT_OPTS = '';
  }
}

async function pickPreviewKaomoji() {
  const fallbackEmoji = '(^_^)';
  const previewCount = 6;
  const buildFallbackPreview = () => Array.from({ length: previewCount }, () => fallbackEmoji).join('\n\n');
  try {
    const kaomojiPath = path.join(scriptDir, 'KaomojiList', 'kaomojis.json');
    const groups = require(kaomojiPath);
    const emoticons = [];
    for (const group of groups || []) {
      for (const category of group?.categories || []) {
        if (Array.isArray(category?.emoticons)) {
          emoticons.push(...category.emoticons);
        }
      }
    }
    if (emoticons.length === 0) {
      return buildFallbackPreview();
    }
    const picks = [];
    for (let i = 0; i < previewCount; i += 1) {
      const index = Math.floor(Math.random() * emoticons.length);
      const candidate = emoticons[index];
      if (typeof candidate === 'string' && candidate.length > 0) {
        picks.push(candidate);
      } else {
        picks.push(fallbackEmoji);
      }
    }
    return picks.join('\n\n');
  } catch (error) {
    if (typeof logEvent === 'function') {
      try {
        await logEvent(`pickPreviewKaomoji: failed to load kaomoji: ${error?.message}`);
      } catch {
        // Ignore logging failures; preview falls back to ASCII kaomoji.
      }
    }
    return buildFallbackPreview();
  }
}

// ============================================================================
// VALIDATION FUNCTIONS (Defensive Programming)
// ============================================================================

/**
 * Validates that a value is a non-empty string.
 * @param {*} value - The value to validate
 * @param {string} fieldName - Name of the field for error messages
 * @throws {Error} If validation fails
 */
function assertNonEmptyString(value, fieldName) {
  if (typeof value !== 'string') {
    throw new Error(`${fieldName} must be a string, got ${typeof value}`);
  }
  if (value.length === 0) {
    throw new Error(`${fieldName} cannot be empty`);
  }
}

/**
 * Validates that a string has reasonable length.
 * @param {string} value - The string to validate
 * @param {string} fieldName - Name of the field for error messages
 * @param {number} maxLength - Maximum allowed length
 * @throws {Error} If validation fails
 */
function assertMaxLength(value, fieldName, maxLength) {
  assertNonEmptyString(value, fieldName);
  if (value.length > maxLength) {
    throw new Error(`${fieldName} exceeds max length of ${maxLength} (got ${value.length})`);
  }
}

/**
 * Validates a tmux session name.
 * Session names must:
 * - Be non-empty strings
 * - Not exceed 100 characters
 * - Not contain: colons (:), periods (.), newlines, control characters
 * - Only contain alphanumeric, underscore, hyphen, and space characters
 * @param {*} sessionName - The session name to validate
 * @throws {Error} If validation fails
 */
function assertValidSessionName(sessionName) {
  assertNonEmptyString(sessionName, 'Session name');
  assertMaxLength(sessionName, 'Session name', 100);

  // Check for forbidden characters
  if (sessionName.includes(':')) {
    throw new Error('Session name cannot contain colons (:)');
  }
  if (sessionName.includes('.')) {
    throw new Error('Session name cannot contain periods (.)');
  }
  if (sessionName.includes('\n') || sessionName.includes('\r')) {
    throw new Error('Session name cannot contain newlines');
  }

  // Check for control characters (ASCII 0-31 and 127)
  if (/[\x00-\x1F\x7F]/.test(sessionName)) {
    throw new Error('Session name cannot contain control characters');
  }

  // Check for null bytes (extra safety)
  if (sessionName.includes('\0')) {
    throw new Error('Session name cannot contain null bytes');
  }

  // Only allow safe characters: alphanumeric, underscore, hyphen, space
  if (!/^[a-zA-Z0-9_\-\s]+$/.test(sessionName)) {
    throw new Error('Session name can only contain letters, numbers, underscore, hyphen, and spaces');
  }
}

/**
 * Validates an action name.
 * @param {*} action - The action to validate
 * @throws {Error} If validation fails
 */
function assertValidAction(action) {
  const validActions = [
    'switch', 'new', 'rename', 'detach', 'kill', 'kill-single',
    'reload-sessions', 'popup-switch',
    'worktree-switch', 'popup-worktree-switch',
    'capital-switch', 'popup-capital-switch'
  ];

  if (typeof action !== 'string') {
    throw new Error(`Action must be a string, got ${typeof action}`);
  }

  if (!validActions.includes(action)) {
    throw new Error(`Invalid action: ${action}. Must be one of: ${validActions.join(', ')}`);
  }
}

/**
 * Validates an array of items (e.g., for fzf input).
 * @param {*} items - The items array to validate
 * @param {string} fieldName - Name of the field for error messages
 * @throws {Error} If validation fails
 */
function assertValidItemsArray(items, fieldName) {
  if (!Array.isArray(items)) {
    throw new Error(`${fieldName} must be an array, got ${typeof items}`);
  }

  if (items.length === 0) {
    throw new Error(`${fieldName} cannot be empty`);
  }

  // Check each item is a string and has reasonable length
  for (let i = 0; i < items.length; i++) {
    if (typeof items[i] !== 'string') {
      throw new Error(`${fieldName}[${i}] must be a string, got ${typeof items[i]}`);
    }
    if (items[i].length > 1000) {
      throw new Error(`${fieldName}[${i}] exceeds max length of 1000 characters`);
    }
  }

  // Sanity check: total items shouldn't be excessive
  if (items.length > 10000) {
    throw new Error(`${fieldName} has too many items: ${items.length} (max 10000)`);
  }
}

/**
 * Validates fzf options strings.
 * @param {*} value - The options string to validate
 * @param {string} fieldName - Name of the field for error messages
 * @throws {Error} If validation fails
 */
function assertValidFzfOptions(value, fieldName) {
  if (typeof value !== 'string') {
    throw new Error(`${fieldName} must be a string, got ${typeof value}`);
  }

  // Max reasonable length for options
  if (value.length > 10000) {
    throw new Error(`${fieldName} exceeds max length of 10000 characters`);
  }

  // Check for command injection attempts
  if (value.includes('\0')) {
    throw new Error(`${fieldName} cannot contain null bytes`);
  }
}

/**
 * Validates a header string for fzf.
 * @param {*} header - The header to validate
 * @throws {Error} If validation fails
 */
function assertValidHeader(header) {
  if (header === null || header === undefined) {
    return; // Header is optional
  }

  if (typeof header !== 'string') {
    throw new Error(`Header must be a string, got ${typeof header}`);
  }

  if (header.length > 500) {
    throw new Error(`Header exceeds max length of 500 characters`);
  }

  // No newlines in headers
  if (header.includes('\n')) {
    throw new Error('Header cannot contain newlines');
  }
}

// ============================================================================
// MAIN SCRIPT
// ============================================================================

async function logEvent(message) {
  try {
    const timestamp = new Date().toISOString();
    const logLine = `${timestamp} ${message}\n`;

    // Check if rotation is needed
    let needsRotation = false;
    try {
      const stats = await fsp.stat(logFilePath);
      needsRotation = stats.size > LOG_MAX_BYTES;
    } catch (error) {
      // File doesn't exist yet, no rotation needed
      needsRotation = false;
    }

    if (needsRotation) {
      // Read entire file, keep only the last LOG_TRIM_TARGET bytes
      const content = await fsp.readFile(logFilePath, 'utf8');
      const lines = content.split('\n');

      // Calculate which lines to keep by working backwards from the end
      let bytesCount = 0;
      let keepFromIndex = lines.length;

      for (let i = lines.length - 1; i >= 0; i--) {
        const lineBytes = Buffer.byteLength(lines[i] + '\n', 'utf8');
        if (bytesCount + lineBytes > LOG_TRIM_TARGET) {
          keepFromIndex = i + 1;
          break;
        }
        bytesCount += lineBytes;
      }

      const kept = lines.slice(keepFromIndex).join('\n');
      await fsp.writeFile(logFilePath, kept + (kept ? '\n' : ''), 'utf8');
    }

    // Append the new log line
    await fsp.appendFile(logFilePath, logLine, 'utf8');
  } catch (error) {
    // Silently fail to avoid breaking the main script
    // Could optionally log to stderr: console.error('Log error:', error);
  }
}
