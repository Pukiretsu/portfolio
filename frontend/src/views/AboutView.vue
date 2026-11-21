<script setup>
import PortfolioPage from '../components/PortfolioPage.vue'
import source from '../content/about.md?raw'
import { readDocument } from '../content/documents'
import { profile } from '../content/profile'

const about = readDocument(source)
</script>

<template>
  <PortfolioPage>
    <article>
      <h1 class="document-title">{{ about.title || 'About me' }}</h1>
      <div class="document-body" v-html="about.html"></div>
    </article>
    <div class="mt-8 flex flex-wrap items-center gap-x-6 gap-y-4">
      <a :href="profile.linkedin" class="primary-button">Connect on LinkedIn <span aria-hidden="true">↗</span></a>
      <a :href="profile.github" class="text-link">GitHub <span aria-hidden="true">↗</span></a>
    </div>
  </PortfolioPage>
</template>
