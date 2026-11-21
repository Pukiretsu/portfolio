<script setup>
import { computed } from 'vue'
import PortfolioPage from '../components/PortfolioPage.vue'
import { posts } from '../content/projects'

const props = defineProps({ slug: String })
const post = computed(() => posts.find(item => item.slug === props.slug))
</script>

<template>
  <PortfolioPage>
    <template v-if="slug">
      <RouterLink to="/projects" class="text-link inline-block">← All projects</RouterLink>
      <article v-if="post" class="mt-7">
        <h1 class="document-title">{{ post.title }}</h1>
        <div class="document-body" v-html="post.html"></div>
      </article>
      <div v-else class="mt-7">
        <h1 class="document-title">Project not found</h1>
        <p class="mt-5 text-muted">Choose a write-up from the projects page.</p>
      </div>
    </template>
    <template v-else>
      <h1 class="document-title">Projects<span class="text-accent">.</span></h1>
      <ul class="mt-8 grid max-w-3xl gap-5">
        <li v-for="item in posts" :key="item.slug">
          <article class="rounded-lg border border-line bg-panel p-6">
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
