#!/usr/bin/env node
// Contrato de saída dos subagentes em .claude/agents.
// - PreToolUse(SubagentHandback): valida o relatório ANTES da entrega; se faltar
//   o formato, bloqueia (exit 2) uma única vez por agente e o agente refaz.
// - Stop/SubagentStop: quando o agente termina em texto (sem handback), valida
//   ali (decision: block, uma vez); em qualquer caso mostra ao usuário o
//   próximo passo do fluxo (systemMessage).
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');

const IMPLEMENTERS = /^(dev-|spec-|qa$|qa-automator$)/;
const REVIEWERS = /^(tl-|fullstack-|sre$)/;

function checkContract(agent, text) {
  const body = text.trim();
  if (!body) return 'o relatório veio vazio';
  if (IMPLEMENTERS.test(agent)) {
    const isPlan = /Plano de Testes:/i.test(body);
    if (!isPlan && !/^#+\s*Verifica[cç][aã]o executada/im.test(body) && !/BLOQUEIO/.test(body)) {
      return 'falta a seção "## Verificação executada" do relatório final (ou `BLOQUEIO:` explicando por que não executou)';
    }
  }
  if (REVIEWERS.test(agent) && /^#+\s*Bloqueantes/im.test(body)) {
    const first = body.split(/\r?\n/).find((l) => l.trim()) ?? '';
    if (!/^\**VEREDITO:/.test(first.trim())) {
      return 'revisão sem `VEREDITO: APROVADO | RESSALVAS` na primeira linha (o orquestrador lê só ela)';
    }
  }
  return null;
}

function nextStep(agent, text) {
  if (/^\**VEREDITO:\s*RESSALVAS/im.test(text)) {
    return 'próximo: ressalvas numeradas voltam ao implementador (3ª falha seguida do mesmo agente → spec-*)';
  }
  if (/^\**VEREDITO:\s*APROVADO/im.test(text)) {
    return 'próximo: com tl-* da stack e tl-qa aprovados, o orquestrador fecha a tarefa e commita';
  }
  const m = agent.match(/^(?:dev|spec)-(\w+)$/);
  if (m) return `próximo: revisão em paralelo por tl-${m[1]}${m[1] === 'qa' ? '' : ' + tl-qa'}`;
  if (agent === 'qa' || agent === 'qa-automator') return 'próximo: revisão por tl-qa';
  return null;
}

// Bloqueia no máximo uma vez por execução de agente (evita laço de reescrita).
function firstBlock(agentId) {
  if (!agentId) return true;
  const mark = path.join(os.tmpdir(), `claude-contract-${String(agentId).replace(/\W/g, '')}`);
  if (fs.existsSync(mark)) return false;
  try { fs.writeFileSync(mark, ''); } catch { /* sem marca, bloqueia uma vez mesmo assim */ }
  return true;
}

function lastHandback(transcriptPath) {
  try {
    const lines = fs.readFileSync(transcriptPath, 'utf8').trim().split('\n');
    for (let i = lines.length - 1; i >= 0; i--) {
      const content = JSON.parse(lines[i]).message?.content;
      if (!Array.isArray(content)) continue;
      const hb = content.find((c) => c.type === 'tool_use' && c.name === 'SubagentHandback');
      if (hb) return String(hb.input?.message ?? '');
    }
  } catch { /* transcript indisponível: sem próximo passo */ }
  return '';
}

let raw = '';
process.stdin.on('data', (c) => { raw += c; });
process.stdin.on('end', () => {
  let input;
  try { input = JSON.parse(raw); } catch { process.exit(0); }
  const agent = String(input.agent_type ?? '').replace(/^.*:/, '');

  if (input.hook_event_name === 'PreToolUse') {
    if (input.tool_name !== 'SubagentHandback') process.exit(0);
    const problem = checkContract(agent, String(input.tool_input?.message ?? ''));
    if (problem && firstBlock(input.agent_id)) {
      process.stderr.write(`Contrato de saída do ${agent}: ${problem}. Refaça o SubagentHandback com o relatório no formato do seu prompt.\n`);
      process.exit(2);
    }
    process.exit(0);
  }

  const finalText = String(input.last_assistant_message ?? '');
  if (finalText.trim()) {
    const problem = checkContract(agent, finalText);
    if (problem && !input.stop_hook_active && firstBlock(input.agent_id)) {
      process.stdout.write(JSON.stringify({
        decision: 'block',
        reason: `Contrato de saída do ${agent}: ${problem}. Reescreva a resposta final no formato do seu prompt.`,
      }));
      process.exit(0);
    }
  }
  const text = finalText.trim() ? finalText : lastHandback(input.agent_transcript_path);
  const step = text ? nextStep(agent, text) : null;
  process.stdout.write(JSON.stringify(step ? { systemMessage: `[${agent}] ${step}` } : {}));
  process.exit(0);
});
