#!/usr/bin/env node
// PreToolUse(Bash) dos subagentes em .claude/agents.
// Bloqueia (exit 2) o que o contrato dos agentes proíbe: versionar, destruir
// trabalho não commitado e mutar ambiente remoto (deploy/apply/infra).
// O motivo vai no stderr e volta ao agente, que deve devolver `BLOQUEIO:`.
'use strict';

const RULES = [
  [/\bgit\b(?:\s+(?:-[Cc]\s+\S+|--?[\w-]+(?:=\S+)?))*\s+(commit|push|pull|merge|rebase|cherry-pick|revert|am|tag(?!\s+(?:-l|--list)\b))\b/,
    'versionar é do orquestrador/usuário (git $1)'],
  [/\bgit\b(?:\s+(?:-[Cc]\s+\S+|--?[\w-]+(?:=\S+)?))*\s+(checkout|restore|switch|clean|stash(?!\s+(?:list|show)\b))\b/,
    'git $1 pode apagar trabalho não commitado — reverta sondas com Edit (lessons/process.md)'],
  [/\bgit\b(?:\s+(?:-[Cc]\s+\S+|--?[\w-]+(?:=\S+)?))*\s+reset\s+.*--hard\b/,
    'git reset --hard apaga trabalho não commitado'],
  [/\bgit\b(?:\s+(?:-[Cc]\s+\S+|--?[\w-]+(?:=\S+)?))*\s+(branch\s+-[dD]|push)\b/, 'operação de branch remota/destrutiva'],
  [/\bsam\s+(deploy|delete|sync)\b/, 'deploy/remoção de stack (sam $1) exige confirmação do usuário'],
  [/\bcdk\s+(deploy|destroy)\b/, 'cdk $1 exige confirmação do usuário'],
  [/\bterraform\s+(apply|destroy|import|taint|untaint|state\s+(rm|mv|push))\b/, 'terraform $1 exige confirmação do usuário'],
  [/\bpulumi\s+(up|destroy)\b/, 'pulumi $1 exige confirmação do usuário'],
  [/\baws\s+s3\s+(rm|rb|mv|sync)\b/, 'aws s3 $1 muta ambiente remoto'],
  [/\baws\s+s3\s+cp\b.*\s+s3:\/\/\S+\s*$/, 'aws s3 cp para bucket muta ambiente remoto'],
  [/\baws\s+(?!s3\b)[\w-]+\s+(create|delete|update|put|remove|attach|detach|terminate|invoke|deploy|execute|set|modify|reboot|restore|rotate|disable|enable|tag|untag|upload|import|publish|send|run|start-(?!query\b))[\w-]*\b/,
    'chamada AWS mutável ($1…) exige confirmação do usuário'],
  [/\bkubectl\s+(apply|delete|create|patch|replace|scale|rollout\s+(restart|undo)|edit|drain|cordon|uncordon|set)\b/, 'kubectl $1 muta o cluster'],
  [/\bhelm\s+(install|upgrade|uninstall|rollback|delete)\b/, 'helm $1 muta o cluster'],
  [/\bgh\s+(pr\s+(create|merge|close|review|comment|edit)|release\s+(create|delete|edit)|workflow\s+run|run\s+(rerun|cancel)|repo\s+(delete|create|edit)|secret\s+(set|delete)|issue\s+(create|close|comment|edit))\b/,
    'gh $1 publica/muta no GitHub'],
  [/\b(npm|pnpm|yarn)\s+publish\b/, 'publicação de pacote'],
  [/\bdocker\s+push\b/, 'docker push publica imagem'],
  [/\brm\s+-[a-zA-Z]*[rR][a-zA-Z]*\s+(\/|~|\$HOME|[A-Za-z]:[\\/]?)(\s|$)/, 'rm recursivo na raiz/home'],
];

let raw = '';
process.stdin.on('data', (c) => { raw += c; });
process.stdin.on('end', () => {
  let cmd = '';
  try { cmd = String(JSON.parse(raw).tool_input?.command ?? ''); } catch { process.exit(0); }
  for (const [re, why] of RULES) {
    const m = cmd.match(re);
    if (m) {
      const reason = why.replace(/\$(\d)/g, (_, i) => m[Number(i)] ?? '');
      process.stderr.write(
        `Bloqueado pelo guard de subagente: ${reason}. ` +
        'Não tente contornar: registre como `BLOQUEIO:` no relatório, com o comando e o motivo.\n');
      process.exit(2);
    }
  }
  process.exit(0);
});
