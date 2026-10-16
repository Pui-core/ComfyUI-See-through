#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

// Check packaging only. MOC3 validity and motion require a Cubism runtime.
const input = process.argv[2];
if (!input) {
  console.error('Usage: node tools/check-live2d-bundle.mjs /path/Model.model3.json');
  process.exit(1);
}
const modelPath = fs.realpathSync(input);
const root = path.dirname(modelPath);
const model = JSON.parse(fs.readFileSync(modelPath, 'utf8'));
assert.equal(model.Version, 3, 'Expected model3 Version 3');
const refs = model.FileReferences;
assert(refs && typeof refs.Moc === 'string', 'Missing MOC3 reference');
assert(Array.isArray(refs.Textures) && refs.Textures.length > 0, 'Missing textures');
const files = new Set();
function resolveReference(ref) {
  assert(typeof ref === 'string' && ref.length > 0, 'Empty file reference');
  assert(!path.isAbsolute(ref) && !ref.includes('\\') && !ref.includes(':'), `Invalid relative path: ${ref}`);
  const target = fs.realpathSync(path.resolve(root, ref));
  assert(target.startsWith(root + path.sep), `File outside model folder: ${ref}`);
  assert(fs.statSync(target).isFile(), `Not a file: ${ref}`);
  files.add(target);
  return target;
}
const moc = fs.readFileSync(resolveReference(refs.Moc));
assert(moc.length > 64 && moc.subarray(0, 4).equals(Buffer.from('MOC3')), 'Missing MOC3 signature');
const textures = refs.Textures.map(ref => {
  const png = fs.readFileSync(resolveReference(ref));
  assert(png.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])), `Expected PNG: ${ref}`);
  const width = png.readUInt32BE(16), height = png.readUInt32BE(20);
  assert(width > 0 && height > 0, `Empty texture: ${ref}`);
  return { file: ref, width, height };
});
for (const key of ['Physics', 'Pose', 'DisplayInfo', 'UserData']) {
  if (refs[key]) JSON.parse(fs.readFileSync(resolveReference(refs[key]), 'utf8'));
}
let expressionCount = 0;
for (const expression of refs.Expressions ?? []) {
  assert(typeof expression.Name === 'string' && expression.Name.length > 0, 'Missing expression name');
  const data = JSON.parse(fs.readFileSync(resolveReference(expression.File), 'utf8'));
  assert.equal(data.Type, 'Live2D Expression', 'Expected exp3 expression type');
  assert(Array.isArray(data.Parameters), 'Missing expression parameters');
  for (const parameter of data.Parameters) {
    assert(typeof parameter.Id === 'string' && parameter.Id.length > 0, 'Missing expression parameter ID');
    assert(Number.isFinite(parameter.Value), 'Expression value must be finite');
    assert(['Add', 'Multiply', 'Overwrite'].includes(parameter.Blend ?? 'Add'), 'Unknown expression blend mode');
  }
  for (const key of ['FadeInTime', 'FadeOutTime']) {
    if (data[key] !== undefined) assert(Number.isFinite(data[key]), 'Invalid expression fade');
  }
  expressionCount++;
}
let motionCount = 0;
for (const group of Object.values(refs.Motions ?? {})) {
  assert(Array.isArray(group), 'Motion group must be an array');
  for (const motion of group) {
    const data = JSON.parse(fs.readFileSync(resolveReference(motion.File), 'utf8'));
    assert.equal(data.Version, 3, 'Expected motion3 Version 3');
    assert(Array.isArray(data.Curves), 'Missing motion curves');
    if (motion.Sound) resolveReference(motion.Sound);
    motionCount++;
  }
}
console.log(JSON.stringify({
  model: path.basename(modelPath), packagingValid: true,
  referencedFiles: files.size, mocBytes: moc.length, textures, motionCount, expressionCount,
  note: 'Reference and header checks only; validate MOC3 and deformation in a Cubism runtime separately.',
}, null, 2));
