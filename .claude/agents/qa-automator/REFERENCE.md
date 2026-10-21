# Referência — qa-automator

Catálogo de consulta do agente `qa-automator`, extraído do `AGENT.md` para manter o prompt enxuto. Sem frontmatter de propósito: o Claude Code trata este arquivo como documentação, não como agente.

## Stack de testes (2026)

### Unit & integração (JS/TS)
- **Vitest** — runner principal (ESM nativo); Jest só em projeto que já usa.
- **@testing-library/react** (ou `@testing-library/dom` em vanilla) — queries por papel/nome acessível (`getByRole`), não por classe CSS ou `data-testid` como primeira opção.
- **@testing-library/user-event** — sempre via `const user = userEvent.setup()` e `await user.click(...)`.
- **msw v2** (`http`, `HttpResponse`) — mock de **rede** (fetch/XHR). Não serve para IPC.
- `vi.fn()`, `vi.spyOn()`, `vi.mock()` (é içado para o topo do arquivo — dependências do factory precisam de `vi.hoisted`); `vi.useFakeTimers()` em vez de esperar tempo real; restaure com `vi.restoreAllMocks()`/`vi.useRealTimers()` no `afterEach`.
- **@faker-js/faker** com seed fixa (`faker.seed(n)`) quando dado aleatório ajuda — o pacote antigo `faker` foi abandonado e não deve ser usado. Para assert, prefira valores explícitos.

### E2E
- **Playwright** (`@playwright/test`) — locators por papel, auto-wait, `expect(locator).toHaveText` em vez de `waitForTimeout`; traces em falha.
- **Electron:** `_electron.launch()` do Playwright (API ainda marcada como experimental — fixe a versão e isole o helper de launch).

### Projetos Electron + SQLite
- **Banco isolado por teste** com o **mesmo driver da produção** em memória (`better-sqlite3` com `':memory:'`, ou o driver que o projeto usa). Trocar de engine/driver no teste (ex.: `sql.js` quando produção usa `better-sqlite3`) esconde diferença de comportamento — é o "ORM drift" do playbook.
- Migrations reais aplicadas no setup do banco de teste (nunca schema escrito à mão no teste).
- **IPC:** no renderer, faça stub da ponte exposta pelo preload (`window.api` do `contextBridge`) com a mesma assinatura; no main, teste repos/services diretamente sem subir o Electron; tenha ao menos um teste que exercita o handler `ipcMain.handle` real para pegar wiring quebrado.

### Mutação
- **StrykerJS** (`@stryker-mutator/vitest-runner`) quando o projeto adota; em outras stacks, mutmut/cosmic-ray (mutmut 3 depende de fork — no Windows use WSL) ou PIT.

### Nomenclatura
```typescript
describe('ModuleName', () => {
  describe('methodName', () => {
    it('returns X when Y', () => {})
    it('throws Z when W', () => {})
  })
})
```
(Siga o idioma de `describe/it` que o projeto já usa.)

### AAA
```typescript
it('applies the discount to the total', () => {
  // Arrange
  const items = [makeSaleItem({ unitPrice: 10, quantity: 3 })]

  // Act
  const total = computeTotal(items, 5)

  // Assert
  expect(total).toBe(25)
})
```

### Factory para dados de teste
```typescript
function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 1,
    name: 'Test product',
    barcode: '7891234567890',
    price: 9.99,
    stock: 100,
    active: true,
    createdAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}
```
Factories ficam onde o projeto já as guarda (ex.: `tests/factories/`); uma factory compartilhada é contrato — mudar o default dela exige rodar a suíte inteira.
