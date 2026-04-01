import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'

// eslintTechDebt: globally disabled rules below — `no-unused-vars`, `no-useless-escape`.
// TODO(MiroFish-ESLINT): file a tracking ticket (owner: frontend) and re-enable per rule after cleanup.

export default [
  js.configs.recommended,
  ...pluginVue.configs['flat/essential'],
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },
  {
    rules: {
      'vue/multi-word-component-names': 'off',
      // TODO(MiroFish-ESLINT): re-enable `no-unused-vars` once unused bindings are cleaned up (target: lint-hardening milestone)
      'no-unused-vars': 'off',
      // TODO(MiroFish-ESLINT): re-enable `no-useless-escape` after regex/string literal fixes (target: lint-hardening milestone)
      'no-useless-escape': 'off',
    },
  },
  {
    ignores: ['dist/**', 'node_modules/**'],
  },
]
