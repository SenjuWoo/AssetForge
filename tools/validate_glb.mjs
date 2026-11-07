/**
 * Khronos glTF Validator bridge.
 *
 * Usage: node validate_glb.mjs <gltf-validator/index.js> <model.glb>
 * The module path is explicit so the validator can live in a repo-local
 * .tools folder without polluting global Node packages.
 */
import fs from "node:fs";
import { createRequire } from "node:module";

const [modulePath, filePath] = process.argv.slice(2);
if (!modulePath || !filePath) {
  console.error("usage: node validate_glb.mjs <validator-module> <model.glb>");
  process.exit(2);
}

const require = createRequire(import.meta.url);
const validator = require(modulePath);
const bytes = new Uint8Array(fs.readFileSync(filePath));
const report = await validator.validateBytes(bytes, { uri: filePath, maxIssues: 200 });
process.stdout.write(JSON.stringify(report));
