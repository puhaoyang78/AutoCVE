const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

const utilsPath = path.join(__dirname, "..", "src", "pages", "AgentAudit", "utils.ts");
const source = fs.readFileSync(utilsPath, "utf8");
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2020,
  },
  fileName: utilsPath,
}).outputText;

const moduleLike = { exports: {} };
const loadModule = new Function("exports", "module", "require", transpiled);
loadModule(moduleLike.exports, moduleLike, require);

const { dedupeActivityLogs, stripAgentLogPrefix } = moduleLike.exports;

test("activity log deduplication keeps the first visible duplicate", () => {
  const duplicateContent =
    "[Finding Agent] **Evaluating potential vulnerabilities**\n\nI need to keep auditing for vulnerabilities.";

  const logs = [
    {
      id: "hist-1",
      time: "11:04:20",
      type: "thinking",
      title: duplicateContent,
      content: duplicateContent,
      agentName: "Finding",
    },
    {
      id: "runtime-1",
      time: "11:04:20",
      type: "thinking",
      title: "**Evaluating potential vulnerabilities**",
      content: "**Evaluating potential vulnerabilities**\n\nI need to keep auditing for vulnerabilities.",
      agentName: "Finding",
    },
    {
      id: "recon-1",
      time: "11:04:21",
      type: "thinking",
      title: "Recon summary",
      content: "Mapped repository routes.",
      agentName: "Recon",
    },
  ];

  const deduped = dedupeActivityLogs(logs);
  assert.deepStrictEqual(
    deduped.map(item => item.id),
    ["hist-1", "recon-1"]
  );
});

test("agent log prefix stripping removes backend labels", () => {
  const content =
    "[Finding Agent] **Evaluating potential vulnerabilities**\n\nI need to keep auditing for vulnerabilities.";

  assert.strictEqual(
    stripAgentLogPrefix(content),
    "**Evaluating potential vulnerabilities**\n\nI need to keep auditing for vulnerabilities."
  );
});
