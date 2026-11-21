<script setup>
import { nextTick, ref } from 'vue'

import PortfolioPreferences from '../components/PortfolioPreferences.vue'
import { t } from '../content/preferences'
import { profile } from '../content/profile'

const menuOpen = ref(false)
const projects = [
  {
    id: 'food-delivery',
    title: 'Food delivery observability',
    summary: 'An event-driven AWS data pipeline for monitoring a simulated food delivery application.',
    flow: ['API Gateway', 'Lambda', 'S3', 'Athena', 'Grafana'],
    details: [
      'AWS Lambda transformed incoming JSON events from API Gateway and stored the data as Parquet in a three-tier data lake backed by three S3 buckets.',
      'Amazon Athena queried the lake, and a Grafana dashboard hosted on Amazon EC2 surfaced the results. Terraform and GitHub Actions automated deployment.',
    ],
    tags: ['AWS', 'Parquet', 'Grafana', 'Terraform', 'GitHub Actions'],
  },
  {
    id: 'air-quality',
    title: 'Bogotá air quality analytics',
    summary: 'A college project that made Bogotá’s air quality data explorable by location and time period.',
    flow: ['Docker crawler', 'Python / pandas', 'Vue / GIS'],
    details: [
      'A Dockerized web crawler collected air quality data. A Python ETL pipeline used pandas to process it, and a Vue site displayed the results with GIS data.',
      'Python microservices generated reports and calculated air quality indices for selected time ranges in Bogotá.',
    ],
    tags: ['Python', 'pandas', 'Docker', 'Vue', 'GIS', 'Microservices'],
  },
]
const stack = [
  { title: 'Cloud infrastructure', tools: ['AWS Lambda', 'API Gateway', 'Amazon S3', 'Amazon Athena', 'Amazon EC2'] },
  { title: 'Data engineering', tools: ['Python', 'pandas', 'ETL', 'Apache Parquet', 'Web crawling'] },
  { title: 'Visualization', tools: ['Grafana', 'Vue', 'GIS'] },
  { title: 'Deployment', tools: ['Terraform', 'GitHub Actions', 'Docker'] },
]
const terminalInput = ref('')
const terminalBody = ref(null)
const responses = {
  help: () => `${t('Available commands')}: whoami, stack, projects, hello, clear`,
  whoami: () => t('Angel. Developer focused on cloud infrastructure, data pipelines, and visualization.'),
  stack: () => stack.map(({ title, tools }) => `${t(title)} / ${tools.map(t).join(', ')}`).join('\n'),
  projects: () => projects.map(({ title, summary }) => `${t(title)} — ${t(summary)}`).join('\n\n'),
  hello: () => t('Hey there. Thanks for stopping by.'),
}
const terminalHistory = ref([{ command: 'whoami', key: 'whoami' }])
function terminalOutput(entry) {
  return Object.hasOwn(responses, entry.key)
    ? responses[entry.key]()
    : `${t('Command not found')}: ${entry.key}. ${t('Type help, then press Enter')}`
}
async function runCommand(value = terminalInput.value) {
  const command = value.trim().toLowerCase()
  terminalInput.value = ''
  if (!command) return
  if (command === 'clear') terminalHistory.value = []
  else {
    terminalHistory.value.push({ command: value.trim(), key: command })
    terminalHistory.value = terminalHistory.value.slice(-20)
  }
  await nextTick()
  terminalBody.value?.scrollTo({ top: terminalBody.value.scrollHeight, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
}
</script>

<template>
  <div class="site-shell">
    <a href="#main" class="skip-link">{{ t("Skip to content") }}</a>
    <header class="site-header">
      <div class="page-width flex flex-wrap items-center justify-between gap-3 py-5">
        <a href="#" class="wordmark" :aria-label="t('Angel portfolio home')">ag<span class="text-accent">.</span></a>
        <nav :aria-label="t('Main navigation')" class="hidden items-center gap-5 lg:flex">
          <RouterLink class="nav-link" to="/projects">{{ t("Projects") }}</RouterLink><a class="nav-link" href="#stack">{{ t("Stack") }}</a><RouterLink class="nav-link" to="/about">{{ t("About") }}</RouterLink><RouterLink class="nav-link" to="/tools">{{ t("Tools") }}</RouterLink>
        </nav>
        <a :href="profile.linkedin" class="header-github hidden items-center gap-3 xl:inline-flex">LinkedIn <span aria-hidden="true">↗</span></a>
        <PortfolioPreferences />
        <button class="menu-toggle lg:hidden" :aria-expanded="menuOpen" aria-controls="mobile-nav" @click="menuOpen = !menuOpen">{{ t(menuOpen ? 'Close' : 'Menu') }} <span aria-hidden="true">{{ menuOpen ? '−' : '+' }}</span></button>
      </div>
      <nav v-if="menuOpen" id="mobile-nav" :aria-label="t('Mobile navigation')" class="page-width flex flex-col gap-5 pb-6 lg:hidden">
        <RouterLink to="/projects" @click="menuOpen = false">{{ t("Projects") }}</RouterLink>
        <a href="#stack" @click="menuOpen = false">{{ t("Stack") }}</a>
        <RouterLink to="/about" @click="menuOpen = false">{{ t("About") }}</RouterLink>
        <RouterLink to="/tools" @click="menuOpen = false">{{ t("Tools") }}</RouterLink>
        <a :href="profile.linkedin">LinkedIn</a>
        <a :href="profile.github">GitHub</a>
      </nav>
    </header>

    <main id="main">
      <section class="page-width section-space grid items-center gap-10 lg:grid-cols-[1.5fr_1fr] lg:gap-16" aria-labelledby="hero-title">
        <div>
          <p class="eyebrow flex items-center gap-3"><span class="tiny-cross" aria-hidden="true">✳</span> {{ t("ANGEL · DEVELOPER") }}</p>
          <h1 id="hero-title" class="mt-5 text-[clamp(2.75rem,6.5vw,5.5rem)] leading-[1.04] font-medium tracking-[-.07em] wrap-anywhere">{{ t("Cloud infrastructure") }}.<br /><span class="text-accent">{{ t("Data pipelines") }}.</span></h1>
          <p class="mt-6 max-w-lg text-base leading-7 text-muted">{{ t("I build data pipelines and the infrastructure behind them, from collecting events to making the results visible in dashboards and maps.") }}</p>
          <div class="mt-8 flex flex-wrap items-center gap-x-6 gap-y-4">
            <a :href="profile.linkedin" class="primary-button">{{ t("Connect on LinkedIn") }} <span aria-hidden="true">↗</span></a>
            <a :href="profile.github" class="text-link">GitHub <span aria-hidden="true">↗</span></a>
          </div>
        </div>
        <nav class="terminal w-full max-w-lg" :aria-label="t('Featured projects')">
          <div class="terminal-title flex items-center justify-between gap-4">
            <div class="window-dots" aria-hidden="true"><i></i><i></i><i></i></div>
            <span>{{ t("Featured projects") }}</span>
            <span aria-hidden="true">⌘</span>
          </div>
          <ul class="divide-y divide-line px-5 sm:px-6">
            <li v-for="project in projects" :key="project.id">
              <a :href="'#' + project.id" class="text-link flex items-center justify-between gap-4 py-5">{{ t(project.title) }} <span class="text-accent" aria-hidden="true">↓</span></a>
            </li>
          </ul>
        </nav>
      </section>

      <section id="work" class="border-y border-line bg-panel section-space" aria-labelledby="work-title">
        <div class="page-width">
          <h2 id="work-title">{{ t("Selected projects") }}<span class="text-accent">.</span></h2>
          <div class="mt-8 grid gap-6 lg:grid-cols-2">
            <article v-for="project in projects" :id="project.id" :key="project.id" class="rounded-lg border border-line bg-base p-5 sm:p-7">
              <h3 class="text-2xl font-medium tracking-tight sm:text-3xl">{{ t(project.title) }}</h3>
              <p class="mt-3 text-sm leading-6 text-soft">{{ t(project.summary) }}</p>
              <ol :aria-label="t('Data flow')" class="my-5 flex flex-wrap items-center gap-x-2 gap-y-3 rounded-md border border-line bg-panel p-3 font-mono text-xs text-accent">
                <li v-for="(step, stepIndex) in project.flow" :key="step" class="inline-flex items-center gap-2">
                  <span v-if="stepIndex > 0" class="text-muted" aria-hidden="true">→</span>{{ t(step) }}
                </li>
              </ol>
              <p v-for="detail in project.details" :key="detail" class="mt-3 text-sm leading-6 text-muted">{{ t(detail) }}</p>
              <ul :aria-label="t('Technologies')" class="mt-5 flex flex-wrap gap-2">
                <li v-for="tag in project.tags" :key="tag" class="tag">{{ t(tag) }}</li>
              </ul>
              <RouterLink :to="{ name: 'project', params: { slug: project.id } }" class="text-link mt-5 inline-block">{{ t("Read the write-up") }} <span aria-hidden="true">→</span></RouterLink>
            </article>
          </div>
        </div>
      </section>

      <section id="stack" class="page-width section-space" aria-labelledby="stack-title">
        <h2 id="stack-title">{{ t("My stack") }}<span class="text-accent">.</span></h2>
        <div class="mt-8 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          <div v-for="group in stack" :key="group.title" class="skill-card">
            <h3 class="text-lg font-semibold">{{ t(group.title) }}</h3>
            <ul class="mt-4 flex flex-wrap gap-2">
              <li v-for="tool in group.tools" :key="tool" class="tag">{{ t(tool) }}</li>
            </ul>
          </div>
        </div>
      </section>

      <section id="about" class="about-section section-space" aria-labelledby="about-title">
        <div class="page-width grid items-start gap-14 lg:grid-cols-2 lg:gap-20">
          <div>
            <h2 id="about-title">{{ t("About me") }}<span class="text-accent">.</span></h2>
            <p class="mt-6 max-w-lg leading-7 text-muted">{{ t("I’m Angel, a developer interested in how data moves through a system, how to automate its deployment, and how to show people what the data says.") }}</p>
            <RouterLink to="/about" class="text-link mt-5 inline-block">{{ t("More about me") }} <span aria-hidden="true">→</span></RouterLink>
          </div>
          <div class="terminal">
            <div class="terminal-title flex items-center justify-between"><div class="window-dots"><i></i><i></i><i></i></div><span>meet-angel.sh</span><span aria-hidden="true">⌘</span></div>
            <div ref="terminalBody" class="terminal-body"><div v-for="(entry, index) in terminalHistory" :key="index" class="mb-5"><p class="terminal-command"><span>visitor@portfolio</span><span class="text-muted">:~$</span> {{ entry.command }}</p><p class="terminal-output">{{ terminalOutput(entry) }}</p></div><form @submit.prevent="runCommand()" class="flex items-center gap-2"><label for="terminal-command" class="shrink-0 text-accent"><span class="sr-only">{{ t("Terminal command") }}</span><span aria-hidden="true">~ $</span></label><input id="terminal-command" v-model="terminalInput" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="160" :placeholder="t('Type help, then press Enter')" class="min-w-0 flex-1 bg-transparent text-ink outline-none" /><button class="terminal-submit" type="submit" :aria-label="t('Run command')">↵</button></form></div>
            <div class="terminal-footer flex flex-wrap items-center gap-3"><span>{{ t("Try") }}</span><button v-for="command in ['help', 'stack', 'hello']" :key="command" @click="runCommand(command)">{{ command }}</button><span class="ml-auto text-muted">{{ t("Interactive terminal") }}</span></div>
          </div>
        </div>
      </section>

      <section id="contact" class="contact-section" aria-labelledby="contact-title">
        <div class="page-width relative py-16 md:py-20">
          <div class="contact-asterisk" aria-hidden="true">✳</div>
          <h2 id="contact-title">{{ t("Let’s connect") }}<span class="text-accent">.</span></h2>
          <div class="relative z-10 mt-8 flex flex-wrap items-center gap-x-6 gap-y-4">
            <a :href="profile.linkedin" class="primary-button">{{ t("Connect on LinkedIn") }} <span aria-hidden="true">↗</span></a>
            <a :href="profile.github" class="text-link">{{ t("Find me on GitHub") }} <span aria-hidden="true">↗</span></a>
          </div>
        </div>
      </section>
    </main>

    <footer class="page-width flex flex-col justify-between gap-5 py-7 text-xs text-muted sm:flex-row sm:items-center"><a href="#" class="wordmark" :aria-label="t('Back to top')">ag<span class="text-accent">.</span></a><span>© {{ new Date().getFullYear() }} {{ profile.name }}</span><a href="#" class="text-link">{{ t("Back to top") }} ↑</a></footer>
  </div>
</template>
