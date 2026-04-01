<template>
  <div class="left-panel report-style" ref="leftPanelRef">
    <div v-if="reportOutline" class="report-content-wrapper">
      <div class="report-header-block">
        <div class="report-meta">
          <span class="report-tag">Prediction Report</span>
          <span class="report-id">ID: {{ reportId || 'REF-2024-X92' }}</span>
        </div>
        <h1 class="main-title">{{ reportOutline.title }}</h1>
        <p class="sub-title">{{ reportOutline.summary }}</p>
        <div class="header-divider"></div>
      </div>

      <div class="sections-list">
        <div
          v-for="(section, idx) in reportOutline.sections"
          :key="idx"
          class="report-section-item"
          :class="{
            'is-active': currentSectionIndex === idx + 1,
            'is-completed': isSectionCompleted(idx + 1),
            'is-pending': !isSectionCompleted(idx + 1) && currentSectionIndex !== idx + 1,
          }"
        >
          <div
            class="section-header-row"
            :class="{ clickable: isSectionCompleted(idx + 1) }"
            @click="onToggle(idx)"
            :role="isSectionCompleted(idx + 1) ? 'button' : undefined"
            :tabindex="isSectionCompleted(idx + 1) ? 0 : undefined"
            :aria-expanded="isSectionCompleted(idx + 1) ? !collapsedSections.has(idx) : undefined"
            :aria-label="isSectionCompleted(idx + 1) ? `Section ${idx + 1}: ${section.title}` : undefined"
            @keydown.enter.prevent="isSectionCompleted(idx + 1) && onToggle(idx)"
            @keydown.space.prevent="isSectionCompleted(idx + 1) && onToggle(idx)"
          >
            <span class="section-number">{{ String(idx + 1).padStart(2, '0') }}</span>
            <h3 class="section-title">{{ section.title }}</h3>
            <svg
              v-if="isSectionCompleted(idx + 1)"
              class="collapse-icon"
              :class="{ 'is-collapsed': collapsedSections.has(idx) }"
              viewBox="0 0 24 24"
              width="20"
              height="20"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"
            >
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>

          <div class="section-body" v-show="!collapsedSections.has(idx)">
            <div
              v-if="generatedSections[idx + 1]"
              class="generated-content"
              v-html="renderMarkdown(generatedSections[idx + 1])"
            ></div>

            <div v-else-if="currentSectionIndex === idx + 1" class="loading-state">
              <div class="loading-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <circle cx="12" cy="12" r="10" stroke-width="4" stroke="#E5E7EB"></circle>
                  <path
                    d="M12 2a10 10 0 0 1 10 10"
                    stroke-width="4"
                    stroke="#4B5563"
                    stroke-linecap="round"
                  ></path>
                </svg>
              </div>
              <span class="loading-text">Generating {{ section.title }}...</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!reportOutline" class="waiting-placeholder" role="status" :aria-label="props.waitingText">
      <div class="waiting-animation" aria-hidden="true">
        <div class="waiting-ring"></div>
        <div class="waiting-ring"></div>
        <div class="waiting-ring"></div>
      </div>
      <span class="waiting-text">{{ waitingText }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  reportOutline: { type: Object, default: null },
  reportId: { type: String, default: '' },
  currentSectionIndex: { type: Number, default: 0 },
  generatedSections: { type: Object, default: () => ({}) },
  collapsedSections: { type: Set, default: () => new Set() },
  renderMarkdown: { type: Function, required: true },
  isSectionCompleted: { type: Function, required: true },
  waitingText: { type: String, default: 'Waiting for Report Agent...' },
});

const emit = defineEmits(['toggle-collapse']);

const leftPanelRef = ref(null);

function onToggle(idx) {
  emit('toggle-collapse', idx);
}

defineExpose({ leftPanelRef });
</script>
