// ESLint 9 flat config — pinado: eslint 9.28.0, @typescript-eslint 8.33.1
import tsPlugin from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';

export default [
  {
    ignores: ['dist/**', 'coverage/**', '.angular/**', 'node_modules/**'],
  },
  {
    files: ['src/**/*.ts'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        project: './tsconfig.json',
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
    },
    rules: {
      // TypeScript recomendado
      ...tsPlugin.configs['recommended'].rules,

      // Barreira arquitetural: SOMENTE src/app/api/api.types.ts pode importar de api/generated.
      // Componentes e services importam de @api/api.types.ts, nunca do gerado. (ADR-0005 §8)
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['**/api/generated/**', '../generated/**', './generated/**'],
              message:
                'Importe de src/app/api/api.types.ts, nunca diretamente de api/generated. (ADR-0005 §8)',
            },
          ],
        },
      ],

      // Qualidade
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/explicit-function-return-type': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],

      // Segurança: proibir innerHTML com dados dinâmicos (XSS)
      'no-restricted-syntax': [
        'error',
        {
          selector: "AssignmentExpression[left.property.name='innerHTML']",
          message: 'Proibido: usar innerHTML com dados dinâmicos (XSS). Use textContent ou binding Angular.',
        },
      ],
    },
  },
  {
    // Exceção RESTRITA: SOMENTE api.types.ts pode importar do gerado (é o único alias permitido).
    // Arquivos de teste (*.spec.ts) e demais de api/ NÃO têm exceção.
    files: ['src/app/api/generated/**/*.ts', 'src/app/api/api.types.ts'],
    rules: {
      'no-restricted-imports': 'off',
    },
  },
];
