<script setup>
import PortfolioPage from '../components/PortfolioPage.vue'
import { computed } from 'vue'
import source from '../content/about.md?raw'
import spanish from '../content/about.es.md?raw'
import portuguese from '../content/about.pt.md?raw'
import { locale, t } from '../content/preferences'
import { readDocument } from '../content/documents'
import { profile } from '../content/profile'

const bios = { en: source, es: spanish, pt: portuguese }
const about = computed(() => readDocument(bios[locale.value]))
</script>

<template>
  <PortfolioPage>
    <article>
      <h1 class="document-title">{{ about.title || t('About me') }}</h1>
      <div class="document-body" v-html="about.html"></div>
    </article>
    <div class="mt-8 flex flex-wrap items-center gap-x-6 gap-y-4">
      <a :href="profile.linkedin" class="primary-button">{{ t("Connect on LinkedIn") }} <span aria-hidden="true">↗</span></a>
      <a :href="profile.github" class="text-link">GitHub <span aria-hidden="true">↗</span></a>
    </div>
  </PortfolioPage>
</template>
