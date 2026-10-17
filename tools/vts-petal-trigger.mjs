#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { performance } from 'node:perf_hooks';
import { createRequire } from 'node:module';

const PLUGIN_NAME = 'Petal Scatter Trigger';
const PLUGIN_DEVELOPER = 'Pui Local Tools';
let websocketClass;

async function loadWebSocket() {
  if (!websocketClass) {
    try {
      // Resolve the isolated development install, or node_modules beside a deployed script.
      const require = createRequire(new URL('./vts-petal-trigger/package.json', import.meta.url));
      websocketClass = (await import(pathToFileURL(require.resolve('ws')).href)).default;
    } catch { throw new ApiError('The pinned ws package is missing. Run npm ci --prefix tools/vts-petal-trigger --ignore-scripts --omit=optional.', true); }
  }
  return websocketClass;
}

export function parseOptions(args) {
  const options = {
    host: '127.0.0.1', port: 8001, modelName: '',
    motionFile: 'PetalScatter.motion3.json', tokenFile: '',
    pollMs: 67, velocity: 70, excursion: 9, windowMs: 1000,
    warmupMs: 750, cooldownMs: 4500, maxGapMs: 800, authorize: false, dryRun: false,
  };
  const names = new Map([
    ['host', 'host'], ['port', 'port'], ['model-name', 'modelName'],
    ['motion-file', 'motionFile'], ['token-file', 'tokenFile'],
    ['poll-ms', 'pollMs'], ['velocity', 'velocity'], ['excursion', 'excursion'],
    ['window-ms', 'windowMs'], ['warmup-ms', 'warmupMs'], ['cooldown-ms', 'cooldownMs'], ['max-gap-ms', 'maxGapMs'],
  ]);
  const numeric = new Set(['port', 'pollMs', 'velocity', 'excursion', 'windowMs', 'warmupMs', 'cooldownMs', 'maxGapMs']);
  for (let i = 0; i < args.length; i++) {
    const argument = args[i];
    if (argument === '--help') return { help: true };
    if (argument === '--authorize') { options.authorize = true; continue; }
    if (argument === '--dry-run') { options.dryRun = true; continue; }
    const key = names.get(argument.startsWith('--') ? argument.slice(2) : '');
    if (!key || !args[i + 1] || args[i + 1].startsWith('--')) throw new Error(`Invalid argument: ${argument}`);
    options[key] = numeric.has(key) ? Number(args[++i]) : args[++i];
  }
  if (!options.modelName || !options.tokenFile) throw new Error('--model-name and --token-file are required.');
  if (!/\.motion3\.json$/i.test(options.motionFile)) throw new Error('--motion-file must name a .motion3.json animation.');
  if (!options.host || /[\s/@?#]/.test(options.host)) throw new Error('--host must be a hostname or IP address.');
  const limits = {
    port: [1, 65535], pollMs: [50, 500], velocity: [10, 720], excursion: [2, 90],
    windowMs: [250, 2500], warmupMs: [250, 5000], cooldownMs: [1000, 60000], maxGapMs: [250, 2000],
  };
  for (const [key, [min, max]] of Object.entries(limits)) {
    if (!Number.isFinite(options[key]) || options[key] < min || options[key] > max) {
      throw new Error(`Invalid ${key}: expected ${min}..${max}.`);
    }
  }
  if (!Number.isInteger(options.port)) throw new Error('Port must be an integer.');
  return options;
}

/** Detect a quick, substantial reversal; static poses and slow turns do not fire. */
export class HeadShakeDetector {
  constructor(options = {}) {
    this.options = { velocity: 70, excursion: 9, windowMs: 1000, warmupMs: 750, cooldownMs: 4500, maxGapMs: 800, ...options };
    this.nextAllowed = -Infinity;
    this.reset();
  }

  reset() {
    this.previousTime = undefined;
    this.foundSince = undefined;
    this.axes = new Map();
  }

  sample({ time, found, x, z }) {
    if (!found || !Number.isFinite(time) || !Number.isFinite(x) || !Number.isFinite(z)) {
      this.reset();
      return false;
    }
    const gap = this.previousTime === undefined ? undefined : time - this.previousTime;
    if (gap !== undefined && (gap <= 0 || gap > this.options.maxGapMs)) this.reset();
    if (this.previousTime === undefined) {
      this.foundSince = time;
      for (const [axis, value] of [['x', x], ['z', z]]) this.axes.set(axis, { value, velocity: 0, leg: null });
      this.previousTime = time;
      return false;
    }
    const dt = time - this.previousTime;
    this.previousTime = time;
    let fire = false;
    const armed = time - this.foundSince >= this.options.warmupMs && time >= this.nextAllowed;
    for (const [axis, input] of [['x', x], ['z', z]]) {
      const state = this.axes.get(axis);
      const previous = state.value;
      state.value += (1 - Math.exp(-dt / 45)) * (input - state.value);
      const velocity = (state.value - previous) * 1000 / dt;
      state.velocity += (1 - Math.exp(-dt / 70)) * (velocity - state.velocity);
      if (!armed) { state.leg = null; continue; }
      if (state.leg && time - state.leg.time > this.options.windowMs) state.leg = null;
      const direction = Math.abs(state.velocity) >= this.options.velocity ? Math.sign(state.velocity) : 0;
      if (!direction) continue;
      if (!state.leg) {
        state.leg = { direction, origin: previous, extreme: state.value, time };
      } else if (direction === state.leg.direction) {
        state.leg.extreme = direction > 0 ? Math.max(state.leg.extreme, state.value) : Math.min(state.leg.extreme, state.value);
      } else {
        if (Math.abs(state.leg.extreme - state.leg.origin) >= this.options.excursion) fire = true;
        state.leg = { direction, origin: previous, extreme: state.value, time };
      }
    }
    if (fire) {
      this.nextAllowed = time + this.options.cooldownMs;
      for (const state of this.axes.values()) state.leg = null;
    }
    return fire;
  }
}

class ApiError extends Error {
  constructor(message, fatal = false) { super(message); this.fatal = fatal; }
}

export class VtsApi {
  constructor(socket) {
    this.socket = socket;
    this.pending = new Map();
    this.sequence = 0;
    socket.addEventListener('message', event => {
      let response;
      try { response = JSON.parse(event.data); } catch { return; }
      const pending = this.pending.get(response.requestID);
      if (!pending) return;
      this.pending.delete(response.requestID);
      clearTimeout(pending.timer);
      if (response.messageType === 'APIError') {
        pending.reject(new ApiError(`VTS API error ${response.data?.errorID ?? 'unknown'} (${pending.type}).`,
          pending.type === 'AuthenticationRequest' || pending.type === 'AuthenticationTokenRequest'));
      } else if (response.messageType !== pending.type.replace(/Request$/, 'Response')) {
        pending.reject(new ApiError(`Unexpected response (${pending.type}).`));
      } else pending.resolve(response.data);
    });
    socket.addEventListener('close', () => this.rejectPending());
    socket.addEventListener('error', () => this.rejectPending());
  }

  static async connect(host, port, signal) {
    const WebSocket = await loadWebSocket();
    const address = host.includes(':') && !host.startsWith('[') ? `[${host}]` : host;
    const socket = new WebSocket(`ws://${address}:${port}`, { perMessageDeflate: false });
    const api = new VtsApi(socket);
    await new Promise((resolve, reject) => {
      const finish = (error) => {
        clearTimeout(timer);
        signal?.removeEventListener('abort', aborted);
        socket.removeEventListener('open', opened);
        socket.removeEventListener('error', failed);
        socket.removeEventListener('close', failed);
        if (error) { socket.close(); reject(error); } else resolve();
      };
      const opened = () => finish();
      const failed = () => finish(new ApiError('VTS connection unavailable.'));
      const aborted = () => finish(new ApiError('Stopped.'));
      const timer = setTimeout(() => finish(new ApiError('VTS connection timed out.')), 6000);
      socket.addEventListener('open', opened);
      socket.addEventListener('error', failed);
      socket.addEventListener('close', failed);
      signal?.addEventListener('abort', aborted, { once: true });
      if (signal?.aborted) aborted();
    });
    return api;
  }

  request(type, data = {}, timeout = 5000) {
    if (this.socket.readyState !== 1) return Promise.reject(new ApiError('VTS disconnected.'));
    const requestID = `petal-${++this.sequence}`;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(requestID);
        reject(new ApiError(`VTS request timed out (${type}).`));
      }, timeout);
      this.pending.set(requestID, { resolve, reject, timer, type });
      this.socket.send(JSON.stringify({ apiName: 'VTubeStudioPublicAPI', apiVersion: '1.0', requestID, messageType: type, data }));
    });
  }

  rejectPending() {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(new ApiError('VTS disconnected.'));
    }
    this.pending.clear();
  }

  close() { this.rejectPending(); this.socket.close(); }
}

function loadToken(tokenFile) {
  try {
    const file = JSON.parse(fs.readFileSync(tokenFile, 'utf8'));
    if (file.pluginName !== PLUGIN_NAME || file.pluginDeveloper !== PLUGIN_DEVELOPER ||
      typeof file.authenticationToken !== 'string' || !file.authenticationToken) {
      throw new ApiError('Token file belongs to a different plugin or has an invalid format.', true);
    }
    return file.authenticationToken;
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    if (error instanceof ApiError) throw error;
    throw new ApiError('Token file could not be read. Keep its contents private.', true);
  }
}

async function authenticate(api, options) {
  let token = loadToken(options.tokenFile);
  if (!token) {
    if (!options.authorize) throw new ApiError('Token file missing. Run once with --authorize and allow the plugin in VTS.', true);
    const result = await api.request('AuthenticationTokenRequest', { pluginName: PLUGIN_NAME, pluginDeveloper: PLUGIN_DEVELOPER }, 120000);
    if (typeof result.authenticationToken !== 'string' || !result.authenticationToken) throw new ApiError('VTS returned an invalid token.', true);
    token = result.authenticationToken;
    try {
      fs.mkdirSync(path.dirname(path.resolve(options.tokenFile)), { recursive: true, mode: 0o700 });
      fs.writeFileSync(options.tokenFile, JSON.stringify({ pluginName: PLUGIN_NAME, pluginDeveloper: PLUGIN_DEVELOPER, authenticationToken: token }, null, 2) + '\n', { mode: 0o600, flag: 'wx' });
    } catch { throw new ApiError('Could not save the private token file. Check its location and permissions before authorizing again.', true); }
  }
  const result = await api.request('AuthenticationRequest', { pluginName: PLUGIN_NAME, pluginDeveloper: PLUGIN_DEVELOPER, authenticationToken: token });
  if (!result.authenticated) throw new ApiError('VTS rejected plugin authentication. Re-authorize this plugin after removing its old private token file.', true);
}

export function findAnimationHotkey(data, motionFile) {
  const name = file => String(file).replaceAll('\\', '/').split('/').at(-1).toLowerCase();
  const matches = (data.availableHotkeys || []).filter(h => h.type === 'TriggerAnimation' && name(h.file) === name(motionFile));
  if (matches.length !== 1) return null;
  return matches[0].hotkeyID || null;
}

function pause(ms, signal) {
  return new Promise(resolve => {
    const finish = () => { clearTimeout(timer); signal?.removeEventListener('abort', finish); resolve(); };
    const timer = setTimeout(finish, ms);
    signal?.addEventListener('abort', finish, { once: true });
    if (signal?.aborted) finish();
  });
}

/** No camera frames are requested. The bridge only reads numeric tracking values. */
export async function watchSession(api, options, detector, { signal, log = console.log, now = () => performance.now(), wait = pause } = {}) {
  let hotkeyID = null;
  let modelID = null;
  let lastState;
  const state = message => { if (message !== lastState) { log(message); lastState = message; } };
  detector.reset();
  while (!signal?.aborted) {
    const started = now();
    const [tracking, face] = await Promise.all([api.request('InputParameterListRequest'), api.request('FaceFoundRequest')]);
    if (signal?.aborted) break;
    const time = now();
    const matching = tracking.modelLoaded && tracking.modelName === options.modelName && tracking.modelID;
    if (!matching || !face.found || time - started > options.maxGapMs) {
      detector.reset();
      if (!matching) { hotkeyID = null; modelID = null; }
      state(!matching ? 'Waiting for the configured model.' : !face.found ? 'Waiting for face tracking.' : 'Waiting for timely tracking updates.');
    } else if (modelID !== tracking.modelID || !hotkeyID) {
      detector.reset();
      const hotkeys = await api.request('HotkeysInCurrentModelRequest');
      if (hotkeys.modelLoaded && hotkeys.modelID === tracking.modelID) {
        hotkeyID = findAnimationHotkey(hotkeys, options.motionFile);
        modelID = hotkeyID ? tracking.modelID : null;
      } else { hotkeyID = null; modelID = null; }
      state(hotkeyID ? 'Petal trigger ready; waiting for a head shake.' : 'Waiting for one matching animation hotkey.');
      if (!hotkeyID) await wait(2000, signal);
    } else {
      const values = new Map((tracking.defaultParameters || []).map(p => [p.name, p.value]));
      const x = values.get('FaceAngleX');
      const z = values.get('FaceAngleZ');
      if (!Number.isFinite(x) || !Number.isFinite(z)) {
        detector.reset();
        state('Waiting for FaceAngleX and FaceAngleZ tracking parameters.');
      } else {
        state('Petal trigger ready; waiting for a head shake.');
        if (detector.sample({ time, found: true, x, z })) {
          // Recheck before invoking a hotkey, so a model switch cannot reuse a stale trigger.
          const [current, currentFace] = await Promise.all([api.request('CurrentModelRequest'), api.request('FaceFoundRequest')]);
          if (current.modelLoaded && current.modelID === modelID && current.modelName === options.modelName && currentFace.found && now() - time <= options.maxGapMs) {
            if (!options.dryRun) await api.request('HotkeyTriggerRequest', { hotkeyID });
            log(options.dryRun ? 'Head shake detected (dry run).' : 'Petal scatter triggered.');
          } else detector.reset();
        }
      }
    }
    await wait(Math.max(0, options.pollMs - (now() - started)), signal);
  }
  detector.reset();
}

export async function run(options, signal, log = console.log) {
  if (!loadToken(options.tokenFile) && !options.authorize) throw new ApiError('Token file missing. Run once with --authorize and allow the plugin in VTS.', true);
  const detector = new HeadShakeDetector(options);
  let backoff = 1500;
  let lastError;
  while (!signal?.aborted) {
    let api;
    const stopped = () => api?.close();
    try {
      api = await VtsApi.connect(options.host, options.port, signal);
      signal?.addEventListener('abort', stopped, { once: true });
      if (signal?.aborted) { api.close(); break; }
      await authenticate(api, options);
      log('Connected to VTube Studio.');
      lastError = undefined;
      backoff = 1500;
      await watchSession(api, options, detector, { signal, log });
    } catch (error) {
      detector.reset();
      if (error.fatal) throw error;
      if (!signal?.aborted && error.message !== lastError) { log(error.message); lastError = error.message; }
    } finally { signal?.removeEventListener('abort', stopped); api?.close(); }
    if (!signal?.aborted) {
      await pause(backoff, signal);
      backoff = Math.min(15000, backoff * 1.5);
    }
  }
}

function help() {
  console.log(`Usage: node vts-petal-trigger.mjs --model-name NAME --token-file PRIVATE.json [options]

--host HOST              VTS host (default 127.0.0.1)
--port PORT              VTS API port (default 8001)
--motion-file FILE       One-time animation (default PetalScatter.motion3.json)
--authorize              Request permission once if the private token file is missing
--dry-run                Detect shakes without playing the animation
--velocity DEG_PER_SEC   Minimum reversal speed (default 70)
--excursion DEGREES      Minimum outgoing motion (default 9)
--window-ms MS           Maximum time before reversal (default 1000)
--warmup-ms MS           Continuous tracking required after reset (default 750)
--cooldown-ms MS         Minimum time between animations (default 4500)
--max-gap-ms MS          Reset after a sampling/response gap (default 800)
--poll-ms MS             Sampling interval, 50..500 (default 67)

Requires Node.js 22+ and the pinned ws package. No camera access is used.`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const controller = new AbortController();
  process.once('SIGINT', () => controller.abort());
  process.once('SIGTERM', () => controller.abort());
  try {
    const options = parseOptions(process.argv.slice(2));
    if (options.help) help();
    else if (Number(process.versions.node.split('.')[0]) < 22) throw new Error('Node.js 22 or newer is required.');
    else await run(options, controller.signal, message => console.log(`${new Date().toISOString()} ${message}`));
  } catch (error) {
    // Avoid printing API payloads, request bodies or private token contents.
    console.error(error instanceof ApiError ? error.message : 'Petal trigger failed. Check its arguments, private token path and local VTS connection.');
    process.exitCode = 1;
  }
}
