import { defineStore } from 'pinia'

export const useUiStore = defineStore('ui', {
  state: () => ({
    toastMessage: '',
    toastVisible: false,
    /** @type {ReturnType<typeof setTimeout> | null} */
    toastTimer: null,
  }),
  actions: {
    showToast(message, durationMs = 4500) {
      this.toastMessage = message
      this.toastVisible = true
      if (this.toastTimer != null) clearTimeout(this.toastTimer)
      this.toastTimer = setTimeout(() => {
        this.toastVisible = false
        this.toastTimer = null
      }, durationMs)
    },
  },
})
