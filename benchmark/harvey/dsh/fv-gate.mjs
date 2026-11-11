// fv-gate: the Firm Verifier (fv_* tools) for Harvey LAB firm-knowledge, in two modes.
//
//   mode "late"  (the reported system, "verify late"): the root agent works exactly as plain DSH, with no fv_* tool
//                and no verifier text. When its turn is about to end (it replied without a tool call), the plugin
//                (1) snapshots output/ as the pre-verification answer, (2) registers the fv_* tools and (3) steers one
//                user message asking it to verify every listed matter (and, with `complete`, to check completeness).
//                The next time the turn ends, it ends. Subagents are never gated.
//   mode "start" (ablation): the fv_* tools are registered from the first step; the usage text is in the system
//                prompt (set by the run's spec).
//
// The tools call the Firm Verifier service (vrag_harvey: python -m vharvey.fv.server), a deterministic lookup over a
// frozen offline index; schemas and messages come from assets.json (python -m vharvey.fv.dsh_assets), shared with
// the LAB-harness arms. Every call is appended to <run>/fv/calls.jsonl; gate events to <run>/fv/gate.jsonl. <run> is
// the directory above DSH_BENCH_ANSWERS_DIR (set by dsh_bench.launch).
//
// Row:
//   - insert:
//       - id: fv-gate
//         name: __BENCH_REPO__/benchmarks/harvey/plugins/fv-gate.mjs
//         config: {mode: late, complete: true, url: http://127.0.0.1:3150, assets: __BENCH_REPO__/benchmarks/harvey/fv/assets.json}
import { appendFileSync, cpSync, existsSync, mkdirSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HERE = fileURLToPath(new URL('.', import.meta.url))
const DSH_ROOT = process.env.DSH_BENCH_DSH_ROOT ?? resolve(HERE, '../../../work/deepseek-harness')
const { defineTool } = await import(pathToFileURL(`${DSH_ROOT}/packages/core/tools/lib/index.js`).href)
const { createUserMessage } = await import(pathToFileURL(`${DSH_ROOT}/packages/llm/llm/lib/index.js`).href)

export const name = 'fv-gate'
export const inject = ['tools']

const SOURCE = { kind: 'plugin', plugin: 'fv-gate' }
const TEXT_OUTPUT = {
  schema: { type: 'object', additionalProperties: false, properties: { text: { type: 'string', required: true } } },
  render: (_args, value) => [{ type: 'text', text: value.text }],
}

/** JSON Schema (OpenAI tool format) -> DSH's author schema: per-property `required: true`, explicit openness. */
function toValue(schema) {
  if (schema.type === 'array') return { type: 'array', ...(schema.items ? { items: toValue(schema.items) } : {}) }
  if (schema.type === 'object') return { type: 'object', properties: toProps(schema), additionalProperties: true }
  return { type: schema.type }
}

function toProps(schema) {
  const req = new Set(schema.required ?? [])
  const props = {}
  for (const [key, prop] of Object.entries(schema.properties ?? {})) {
    props[key] = { ...toValue(prop), ...(prop.description ? { description: prop.description } : {}),
      ...(req.has(key) ? { required: true } : {}) }
  }
  return props
}

function runDir() {
  const answers = process.env.DSH_BENCH_ANSWERS_DIR
  return answers ? dirname(answers) : null
}

function log(file, entry) {
  const dir = runDir()
  if (!dir) return
  mkdirSync(join(dir, 'fv'), { recursive: true })
  appendFileSync(join(dir, 'fv', file), JSON.stringify({ t: new Date().toISOString(), ...entry }) + '\n')
}

export function apply(ctx, config = {}) {
  const mode = config.mode ?? 'late'
  if (!['late', 'start'].includes(mode)) throw new Error(`fv-gate: unknown mode ${mode}`)
  if (!config.url || !config.assets) throw new Error('fv-gate: config.url and config.assets are required')
  const assets = JSON.parse(readFileSync(config.assets, 'utf8'))
  const schemas = [...assets.tools, ...(config.complete ? [assets.complete_tool] : [])]

  const definitions = schemas.map(schema => defineTool({
    name: schema.name,
    description: schema.description,
    parameters: toProps(schema.parameters),
    output: TEXT_OUTPUT,
    async execute(args, exec) {
      let text
      try {
        const res = await fetch(`${config.url}/fv/${schema.name}`, {
          method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(args ?? {}),
        })
        text = await res.text()
      } catch (error) {
        text = JSON.stringify({ error: `verifier unavailable: ${String(error)}` })
      }
      log('calls.jsonl', { tool: schema.name, args, result: JSON.parse(text), agent: exec.agent?.session?.id })
      return { text }
    },
  }))
  let registered = false
  const register = () => {
    if (registered) return
    registered = true
    for (const d of definitions) ctx.tools.register(d)
  }

  if (mode === 'start') {
    register()
    log('gate.jsonl', { event: 'tools-from-start', tools: schemas.map(s => s.name) })
    return
  }

  const gated = new Set() // root session ids that already passed the gate (one verification request per run)
  ctx.on('agent/turn-stopping', async ({ agent, turn }) => {
    const header = agent.session?.header ?? {}
    if (header.parentSession !== undefined) return // subagent
    const key = header.id ?? 'root'
    if (gated.has(key)) return
    gated.add(key)
    const dir = runDir()
    const output = join(process.cwd(), 'output')
    if (dir && existsSync(output)) cpSync(output, join(dir, 'fv', 'pregate', 'output'), { recursive: true })
    register()
    const text = config.complete ? assets.late_message_complete : assets.late_message
    log('gate.jsonl', { event: 'gate', turn, snapshot: Boolean(dir && existsSync(output)), tools: schemas.map(s => s.name) })
    agent.steer(createUserMessage({ content: [{ type: 'text', text }], source: SOURCE }))
  })
}
