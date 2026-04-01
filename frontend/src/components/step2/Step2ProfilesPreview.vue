<template>
  <div v-if="profiles.length > 0" class="profiles-preview">
    <div class="preview-header">
      <span class="preview-title">Generated Agent Personas</span>
    </div>
    <div class="profiles-list" role="list">
      <div
        v-for="(profile, idx) in profiles"
        :key="profileKey(profile, idx)"
        class="profile-card"
        role="listitem"
        tabindex="0"
        :aria-label="`Agent ${profile.username || profile.name || idx + 1}`"
        @click="$emit('select', profile)"
        @keydown.enter.prevent="$emit('select', profile)"
        @keydown.space.prevent="$emit('select', profile)"
      >
        <div class="profile-header">
          <span class="profile-realname">{{ profile.username || 'Unknown' }}</span>
          <span class="profile-username">@{{ profile.name || `agent_${idx}` }}</span>
        </div>
        <div class="profile-meta">
          <span class="profile-profession">{{ profile.profession || 'Unknown profession' }}</span>
        </div>
        <p class="profile-bio">{{ profile.bio || 'No bio available' }}</p>
        <div v-if="profile.interested_topics?.length" class="profile-topics">
          <span
            v-for="(topic, topicIdx) in profile.interested_topics.slice(0, 3)"
            :key="`${topic}-${topicIdx}`"
            class="topic-tag"
          >{{ topic }}</span>
          <span v-if="profile.interested_topics.length > 3" class="topic-more">
            +{{ profile.interested_topics.length - 3 }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  profiles: {
    type: Array,
    default: () => []
  }
})

defineEmits(['select'])

function profileKey(profile, idx) {
  const withIdx = (base) => `${base}|${idx}`
  if (profile.user_id != null && profile.user_id !== '') return withIdx(String(profile.user_id))
  if (profile.agent_id != null && profile.agent_id !== '') return withIdx(String(profile.agent_id))
  if (profile.username) return withIdx(String(profile.username))
  if (profile.id != null && profile.id !== '') return withIdx(String(profile.id))
  if (profile.email) return withIdx(String(profile.email))
  return String(idx)
}
</script>

<style scoped>
.profiles-preview {
  margin-top: 1.25rem;
  border-top: 1px solid #e5e5e5;
  padding-top: 1rem;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.preview-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.03125rem;
}

.profiles-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
  max-height: 20rem;
  overflow-y: auto;
  padding-right: 0.25rem;
  scrollbar-width: thin;
  scrollbar-color: #ddd #fff;
}

.profiles-list::-webkit-scrollbar {
  width: 4px;
}

.profiles-list::-webkit-scrollbar-thumb {
  background: #ddd;
  border-radius: 2px;
}

.profiles-list::-webkit-scrollbar-thumb:hover {
  background: #ccc;
}

.profile-card {
  background: #fafafa;
  border: 1px solid #e5e5e5;
  border-radius: 6px;
  padding: 0.875rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.profile-card:hover {
  border-color: #999;
  background: #fff;
}

.profile-card:focus-visible {
  border-color: #999;
  background: #fff;
  outline: 2px solid #1d4ed8;
  outline-offset: 2px;
}

.profile-header {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  margin-bottom: 0.375rem;
}

.profile-realname {
  font-size: 0.875rem;
  font-weight: 700;
  color: #000;
}

.profile-username {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6875rem;
  color: #999;
}

.profile-meta {
  margin-bottom: 0.5rem;
}

.profile-profession {
  font-size: 0.6875rem;
  color: #666;
  background: #f0f0f0;
  padding: 0.125rem 0.5rem;
  border-radius: 3px;
}

.profile-bio {
  font-size: 0.75rem;
  color: #444;
  line-height: 1.6;
  margin: 0 0 0.625rem 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.profile-topics {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.topic-tag {
  font-size: 0.625rem;
  color: #1565c0;
  background: #e3f2fd;
  padding: 0.125rem 0.5rem;
  border-radius: 10px;
}

.topic-more {
  font-size: 0.625rem;
  color: #999;
  padding: 0.125rem 0.375rem;
}

@media (max-width: 640px) {
  .profiles-list {
    grid-template-columns: 1fr;
  }
}
</style>
