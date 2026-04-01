import { ref, computed } from 'vue'

/**
 * Shared dual-panel layout (graph / split / workbench) used across workflow views.
 */
export function useWorkflowLayout(initialMode = 'split') {
  const viewMode = ref(initialMode)

  const leftPanelStyle = computed(() => {
    if (viewMode.value === 'graph') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
    if (viewMode.value === 'workbench') return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
    return { width: '50%', opacity: 1, transform: 'translateX(0)' }
  })

  const rightPanelStyle = computed(() => {
    if (viewMode.value === 'workbench') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
    if (viewMode.value === 'graph') return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
    return { width: '50%', opacity: 1, transform: 'translateX(0)' }
  })

  const toggleMaximize = (target) => {
    viewMode.value = viewMode.value === target ? 'split' : target
  }

  return { viewMode, leftPanelStyle, rightPanelStyle, toggleMaximize }
}
