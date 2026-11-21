<script setup>
import { computed } from 'vue'
import PortfolioPage from '../components/PortfolioPage.vue'
import { projectPosts } from '../content/projects'
import { locale, t } from '../content/preferences'

const posts = computed(() => projectPosts(locale.value))

const props = defineProps({ slug: String })
const post = computed(() => posts.value.find(item => item.slug === props.slug))
</script>

<template>
  <PortfolioPage>
    <template v-if="slug">
      <RouterLink to="/projects" class="text-link inline-block">← {{ t("All projects") }}</RouterLink>
      <article v-if="post" :lang="post.language" class="mt-7">
        <h1 class="document-title">{{ post.title }}</h1>
        <p v-if="post.language !== locale" :lang="locale" class="mt-3 text-sm text-muted">{{ t("Available in English") }}</p>
        <div class="document-body" v-html="post.html"></div>
      </article>
      <div v-else class="mt-7">
        <h1 class="document-title">{{ t("Project not found") }}</h1>
        <p class="mt-5 text-muted">{{ t("Choose a write-up from the projects page.") }}</p>
      </div>
    </template>
    <template v-else>
      <h1 class="document-title">{{ t("Projects") }}<span class="text-accent">.</span></h1>
      <ul class="mt-8 grid max-w-3xl gap-5">
        <li v-for="item in posts" :key="item.slug">
          <article :lang="item.language" class="rounded-lg border border-line bg-panel p-6">
            <h2 class="text-2xl">
              <RouterLink :to="{ name: 'project', params: { slug: item.slug } }" class="hover:text-accent">{{ item.title }}</RouterLink>
            </h2>
            <p v-if="item.summary" class="mt-3 leading-7 text-muted">{{ item.summary }}</p>
          </article>
        </li>
      </ul>
    </template>
  </PortfolioPage>
</template>
