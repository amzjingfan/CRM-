import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { frontendRoot } from "../helpers/paths.mjs";
const require = createRequire(new URL("../../../frontend/package.json", import.meta.url));
const ts = require("typescript");

test("Agent submits immediately without erasing the next input at completion", async () => {
  const source = readFileSync(process.env.AGENT_PREVIEW_SOURCE ?? new URL("app/agents/page.tsx", frontendRoot), "utf8");
  const start = source.indexOf("  async function preview() {");
  const code = source.slice(start, source.indexOf("\n  return <AppShell>", start));
  let input = "First question";
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  const result = {content:"Answer",tool_calls:[],citations:[]};
  const noop = () => {};
  const bindings = {
    previewInput: input, selected:{id:"agent"}, previewBusy:false, dirty:false,
    previewRequestId:{current:0}, previewAbort:{current:null}, conversationId:"", previewMode:"single",
    setPreviewInput:(value) => {input=value;}, setPreviewLines:noop, setPreviewBusy:noop,
    setPreviewError:noop, setPreviewResult:noop, setPreviewDrafts:noop, setLogs:noop,
    debugAgent:async()=>{await pending;return result;},
    streamAgentDebug:async(_id,_text,_conversation,_mode,onEvent)=>{await pending;onEvent({event:"result",data:result});},
    getAgentLogs:async()=>({items:[]}), message:(error)=>error.message,
  };
  const compiled = ts.transpileModule(code, {compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText;
  const run = new Function(...Object.keys(bindings), `${compiled}; return preview;`)(...Object.values(bindings));
  const operation = run();
  try {
    assert.equal(input, "", "submitted text must clear before waiting for model");
    input="Next question";
    release(); await operation;
    assert.equal(input,"Next question","completion must preserve the next draft");
  } finally { release(); await operation; }
});
