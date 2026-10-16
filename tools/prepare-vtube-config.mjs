#!/usr/bin/env node
// Create a local VTube Studio profile from an exported Live2D bundle.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const usage = 'node tools/prepare-vtube-config.mjs <model.model3.json> [--name NAME] [--out FILE] [--force]';

function main() {
  const args = process.argv.slice(2);
  if (!args.length || args.includes('--help')) {
    console.log(usage);
    return;
  }
  const modelPath = path.resolve(args.shift());
  if (!modelPath.endsWith('.model3.json')) throw new Error('Input must be a .model3.json file.');
  const stem = path.basename(modelPath, '.model3.json');
  let name = stem;
  let output = path.join(path.dirname(modelPath), `${stem}.vtube.json`);
  let force = false;
  while (args.length) {
    const option = args.shift();
    if (option === '--force') force = true;
    else if (option === '--name' || option === '--out') {
      const value = args.shift();
      if (!value || value.startsWith('--')) throw new Error(`Missing value for ${option}.`);
      if (option === '--name') name = value;
      else output = path.resolve(value);
    } else throw new Error(`Unknown option: ${option}`);
  }
  if (!output.endsWith('.vtube.json')) throw new Error('Output must end with .vtube.json.');
  if (fs.existsSync(output) && !force) throw new Error('Profile already exists; use --force to replace it.');
  const model = JSON.parse(fs.readFileSync(modelPath, 'utf8'));
  const refs = model.FileReferences;
  if (!refs?.Moc || !Array.isArray(refs.Textures) || !refs.Textures.length) {
    throw new Error('The model must reference a MOC3 and textures.');
  }
  const cdiPath = path.resolve(path.dirname(modelPath), refs.DisplayInfo || `${stem}.cdi3.json`);
  const cdi = JSON.parse(fs.readFileSync(cdiPath, 'utf8'));
  if (!Array.isArray(cdi.Parameters)) throw new Error('Display info must contain Parameters.');
  const available = new Set(cdi.Parameters.map(parameter => parameter.Id));
  const map = (Name, Input, OutputLive2D, InputRangeLower, InputRangeUpper,
    OutputRangeLower, OutputRangeUpper, Smoothing = 15) => ({
    Folder: '', Name, Input, InputRangeLower, InputRangeUpper,
    OutputRangeLower, OutputRangeUpper, ClampInput: true, ClampOutput: true,
    UseBlinking: false, UseBreathing: false, OutputLive2D, Smoothing, Minimized: false,
  });
  const mappings = [
    map('顔の左右', 'FaceAngleX', 'ParamAngleX', -30, 30, -30, 30),
    map('顔の上下', 'FaceAngleY', 'ParamAngleY', -25, 25, -25, 25),
    map('顔の傾き', 'FaceAngleZ', 'ParamAngleZ', -30, 30, -20, 20),
    map('左まぶた', 'EyeOpenLeft', 'ParamEyeLOpen', 0, 0.85, 0, 1, 8),
    map('右まぶた', 'EyeOpenRight', 'ParamEyeROpen', 0, 0.85, 0, 1, 8),
    map('視線左右', 'EyeRightX', 'ParamEyeBallX', -1, 1, 1, -1),
    map('視線上下', 'EyeRightY', 'ParamEyeBallY', -1, 1, -1, 1),
    map('左眉', 'BrowLeftY', 'ParamBrowLY', 0, 1, -0.4, 0.4),
    map('右眉', 'BrowRightY', 'ParamBrowRY', 0, 1, -0.4, 0.4),
    map('口開閉', 'MouthOpen', 'ParamMouthOpenY', 0, 1, 0, 1, 7),
    map('口の形', 'MouthSmile', 'ParamMouthForm', 0, 1, 0, 0.45),
    map('笑顔を自動認識', 'MouthSmile', 'ParamSmile', 0.6, 0.85, 0, 1, 20),
    map('体左右', 'FaceAngleX', 'ParamBodyAngleX', -30, 30, -5, 5, 30),
    map('体上下', 'FaceAngleY', 'ParamBodyAngleY', -25, 25, -3, 3, 30),
    map('体傾き', 'FaceAngleZ', 'ParamBodyAngleZ', -30, 30, -4, 4, 30),
    { ...map('呼吸', '', 'ParamBreath', 0, 1, 0, 0.5, 0), UseBreathing: true },
  ].filter(mapping => available.has(mapping.OutputLive2D));
  if (!mappings.length) throw new Error('No supported Live2D parameter IDs found.');
  const relative = file => path.relative(path.dirname(output), file).split(path.sep).join('/');
  const icon = fs.readdirSync(path.dirname(modelPath))
    .find(file => file.startsWith('ico_') && /\.(png|jpe?g)$/i.test(file));
  const profile = {
    Version: 1, Name: name, ModelID: crypto.randomUUID().replaceAll('-', ''),
    FileReferences: {
      Icon: icon ? relative(path.join(path.dirname(modelPath), icon)) : '',
      Model: relative(modelPath), IdleAnimation: '', IdleAnimationWhenTrackingLost: '',
    },
    ModelPositionMovement: { Use: false, X: 0, Y: 0, Z: 0, SmoothingX: 20, SmoothingY: 20, SmoothingZ: 20 },
    // VTS stores the 30/60/120/app-FPS selector as enum values 0/1/2/3.
    PhysicsSettings: { Use: true, UseLegacyPhysics: false, Live2DPhysicsFPS: 1,
      PhysicsStrength: 50, WindStrength: 0, DraggingPhysicsStrength: 20 },
    GeneralSettings: { ModelVolume: 90, TimeUntilTrackingLostIdleAnimation: 0,
      WorkshopSharingForbidden: true, EnableExpressionSaving: false },
    ParameterSettings: mappings,
    Hotkeys: [
      { HotkeyID: crypto.randomUUID().replaceAll('-', ''), Name: 'Webカメラの開始・停止',
        Action: 'ToggleTracker', File: 'Webcam', Folder: '', IsGlobal: false, IsActive: true,
        Triggers: { Trigger1: '', Trigger2: '', Trigger3: '', ScreenButton: -1 } },
    ], HotkeySettings: { UseOnScreenHotkeys: false, UseKeyboardHotkeys: true,
      SendOnScreenHotkeysToPC: false, OnScreenHotkeyAlpha: 90 },
    SavedActiveExpressions: [], ModelFolder: '<VTS_MODEL_BASE_PATH_PLACEHOLDER>',
  };
  fs.writeFileSync(output, `${JSON.stringify(profile, null, 2)}\n`, { flag: force ? 'w' : 'wx' });
  console.log(JSON.stringify({ profile: output, mappings: mappings.length,
    automaticSmile: mappings.some(mapping => mapping.OutputLive2D === 'ParamSmile') }, null, 2));
}

try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
