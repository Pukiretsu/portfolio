<script setup>
import { languages, locale, t, theme } from '../content/preferences'
</script>

<template>
  <div class="flex shrink-0 items-center gap-2">
    <select v-model="locale" :aria-label="t('Language')" class="preference-control max-w-28">
      <option v-for="(label, code) in languages" :key="code" :value="code" :lang="code">{{ label }}</option>
    </select>
    <button type="button" class="preference-control" :aria-label="t(theme === 'dark' ? 'Light mode' : 'Dark mode')" :title="t(theme === 'dark' ? 'Light mode' : 'Dark mode')" @click="theme = theme === 'dark' ? 'light' : 'dark'">
      <span aria-hidden="true">{{ theme === 'dark' ? '☀' : '☾' }}</span>
    </button>
  </div>
</template>
