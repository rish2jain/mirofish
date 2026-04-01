<template>
  <div class="app-root">
    <div v-if="ui.toastVisible" class="app-toast" role="status">{{ ui.toastMessage }}</div>
    <router-view />
  </div>
</template>

<script setup>
import { storeToRefs } from 'pinia'
import { useUiStore } from './stores/ui'

const uiStore = useUiStore()
const ui = storeToRefs(uiStore)
</script>

<style>
/* Global style reset */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.app-root {
  min-height: 100vh;
}

.app-toast {
  position: fixed;
  bottom: 1.25rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  max-width: min(90vw, 32rem);
  padding: 0.75rem 1rem;
  background: #111;
  color: #fff;
  font-size: 0.875rem;
  line-height: 1.4;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
  border-radius: 2px;
}

#app {
  font-family: 'JetBrains Mono', 'Space Grotesk', 'Noto Sans SC', monospace;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #000000;
  background-color: #ffffff;
}

/* Scrollbar styles */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
}

::-webkit-scrollbar-thumb {
  background: #000000;
}

::-webkit-scrollbar-thumb:hover {
  background: #333333;
}

/* Global button styles */
button {
  font-family: inherit;
}
</style>
