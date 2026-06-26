#!/usr/bin/env node
/**
 * Sentinela: verifica que o arquivo gerado contém o cabeçalho AUTO-GENERATED exato.
 * Falha se o arquivo foi editado manualmente ou gerado sem o header correto (ADR-0005 §8).
 *
 * Uso: node scripts/check-generated-header.mjs
 */
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const filePath = join(__dirname, '..', 'src', 'app', 'api', 'generated', 'openapi-types.ts');

// String exata injetada por gen-api.mjs
const REQUIRED_HEADER = 'AUTO-GENERATED — DO NOT EDIT. Run: npm run gen:api';

let content;
try {
  content = readFileSync(filePath, 'utf-8');
} catch (_err) {
  console.error(`[check-generated-header] ERRO: arquivo não encontrado: ${filePath}`);
  console.error('  Execute: npm run gen:api');
  process.exit(1);
}

if (!content.includes(REQUIRED_HEADER)) {
  console.error('[check-generated-header] ERRO: cabeçalho AUTO-GENERATED ausente ou incorreto.');
  console.error(`  Esperado: "${REQUIRED_HEADER}"`);
  console.error('  O arquivo pode ter sido editado manualmente ou gerado sem npm run gen:api.');
  console.error('  Execute: npm run gen:api');
  process.exit(1);
}

console.log('[check-generated-header] OK: cabeçalho AUTO-GENERATED presente.');
