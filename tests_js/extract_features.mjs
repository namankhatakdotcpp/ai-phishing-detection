// Runs the ACTUAL extension/page_extractor.js source (unmodified,
// read from disk -- not a reimplementation) inside a jsdom-backed
// document/location/window, using Node's vm module to capture the
// script's completion value the same way chrome.scripting.executeScript
// captures a `files` injection's completion value in real Chrome. This
// is what makes it a real parity check rather than a second hand-written
// copy of the extraction logic that could drift independently.
//
// Usage: node extract_features.mjs <html-file-or-"-"> <url>
// Prints the extracted feature JSON to stdout.

import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const EXTRACTOR_PATH = path.join(__dirname, "..", "extension", "page_extractor.js");

function main() {
  const [htmlArg, url] = process.argv.slice(2);
  if (!url) {
    console.error("usage: node extract_features.mjs <html-file-or-'-'> <url>");
    process.exit(2);
  }
  const html = htmlArg === "-" ? "<!DOCTYPE html><html><head></head><body></body></html>" : fs.readFileSync(htmlArg, "utf8");

  const dom = new JSDOM(html, { url });
  const context = vm.createContext({
    document: dom.window.document,
    location: dom.window.location,
    window: dom.window,
    URL: dom.window.URL,
  });

  const source = fs.readFileSync(EXTRACTOR_PATH, "utf8");
  const result = vm.runInContext(source, context, { filename: EXTRACTOR_PATH });

  process.stdout.write(JSON.stringify(result));
}

main();
