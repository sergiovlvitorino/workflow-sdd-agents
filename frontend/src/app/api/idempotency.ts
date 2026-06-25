/**
 * Gerador de Idempotency-Key (P-03).
 *
 * Uso:
 *   const key = generateIdempotencyKey();
 *   this.http.post(url, body, { headers: { 'Idempotency-Key': key } });
 *
 * O service EXIGE a key por parametro — nao gera internamente em cada retry.
 * Isso permite que a UI passe a MESMA key em retentativas da mesma intencao
 * (decisao fechada em T-S3-03, onde ha contexto de intencao de escrita).
 */
export function generateIdempotencyKey(): string {
  return crypto.randomUUID();
}
