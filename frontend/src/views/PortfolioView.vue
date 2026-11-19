<script setup>
import { computed, nextTick, ref } from 'vue'

// Personal details and project content: edit these to make the portfolio your own.
const profile = { name: 'Angel', github: 'https://github.com/Pukiretsu', repository: 'https://github.com/Pukiretsu/portfolio' }
const menuOpen = ref(false)
const activeFilter = ref('All')
const filters = ['All', 'Cloud', 'Frontend', 'Automation']
const projects = [
  { title: 'A home in the cloud.', category: 'Cloud', label: 'THE PLATFORM', description: 'The infrastructure behind this very site. Private by default, delivered at the edge, and defined entirely in code.', tags: ['AWS', 'Terraform', 'Cloudflare'], path: '/tree/main/infra', visual: 'cloud' },
  { title: 'From commit to live.', category: 'Automation', label: 'THE DELIVERY', description: 'A push to main becomes a deployment. Short-lived credentials, reproducible builds, and a refreshed global cache.', tags: ['GitHub Actions', 'OIDC', 'CI/CD'], path: '/tree/main/.github/workflows', visual: 'pipeline' },
  { title: 'A little more human.', category: 'Frontend', label: 'THE EXPERIENCE', description: 'A fast, responsive portfolio built with Vue and Tailwind. A space to experiment, make things, and keep learning.', tags: ['Vue', 'Tailwind CSS', 'Vite'], path: '/tree/main/frontend', visual: 'frontend' },
]
const visibleProjects = computed(() => projects.filter(project => activeFilter.value === 'All' || project.category === activeFilter.value))
const skills = [
  { title: 'Infrastructure as code', description: 'Repeatable foundations. Fewer surprises.', tools: 'Terraform / AWS / Cloudflare', icon: 'layers' },
  { title: 'Build. Ship. Improve.', description: 'Make the path to production a little smoother.', tools: 'GitHub Actions / Git / CI/CD', icon: 'flow' },
  { title: 'Thoughtful interfaces', description: 'Simple experiences, carefully put together.', tools: 'Vue / JavaScript / Tailwind', icon: 'window' },
]
const terminalInput = ref('')
const terminalBody = ref(null)
const responses = {
  help: 'Available commands: whoami, stack, projects, hello, clear',
  whoami: 'Angel. Developer, cloud enthusiast, and perpetual work in progress.\nCurrently building: this little corner of the internet.',
  stack: 'Frontend   Vue + Tailwind + Vite\nCloud      S3 + CloudFront + ACM\nDNS        Cloudflare\nDelivery   Terraform + GitHub Actions + OIDC',
  projects: 'You are looking at one!\nExplore the infrastructure, delivery pipeline, and frontend in the work section.',
  hello: 'Hey there. Thanks for stopping by. Make yourself at home.',
}
const terminalHistory = ref([{ command: 'whoami', output: responses.whoami }])
async function runCommand(value = terminalInput.value) {
  const command = value.trim().toLowerCase()
  terminalInput.value = ''
  if (!command) return
  if (command === 'clear') terminalHistory.value = []
  else {
    terminalHistory.value.push({ command: value.trim(), output: Object.hasOwn(responses, command) ? responses[command] : `Command not found: ${command}. Type "help" to explore.` })
    terminalHistory.value = terminalHistory.value.slice(-20)
  }
  await nextTick()
  terminalBody.value?.scrollTo({ top: terminalBody.value.scrollHeight, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
}
</script>

<template>
  <div class="site-shell">
    <a href="#main" class="skip-link">Skip to content</a>
    <header class="site-header">
      <div class="page-width flex items-center justify-between gap-6 py-5">
        <a href="#" class="wordmark" aria-label="Angel portfolio home">ag<span class="text-accent">.</span></a>
        <nav aria-label="Main navigation" class="hidden items-center gap-8 md:flex">
          <a class="nav-link" href="#work">The work</a><a class="nav-link" href="#about">The person</a><a class="nav-link" href="#contact">Say hello</a><RouterLink class="nav-link" to="/tools">Tools</RouterLink>
        </nav>
        <a :href="profile.github" class="header-github hidden items-center gap-3 md:inline-flex">Find me on GitHub <span aria-hidden="true">↗</span></a>
        <button class="menu-toggle md:hidden" :aria-expanded="menuOpen" aria-controls="mobile-nav" @click="menuOpen = !menuOpen">{{ menuOpen ? 'Close' : 'Menu' }} <span aria-hidden="true">{{ menuOpen ? '−' : '+' }}</span></button>
      </div>
      <nav v-if="menuOpen" id="mobile-nav" aria-label="Mobile navigation" class="page-width flex flex-col gap-5 pb-6 md:hidden">
        <a href="#work" @click="menuOpen = false">The work</a><a href="#about" @click="menuOpen = false">The person</a><a href="#contact" @click="menuOpen = false">Say hello</a><RouterLink to="/tools" @click="menuOpen = false">Tools</RouterLink><a :href="profile.github">GitHub</a>
      </nav>
    </header>

    <main id="main">
      <section class="hero page-width relative" aria-labelledby="hero-title">
        <div class="hero-copy relative z-10">
          <p class="eyebrow flex items-center gap-3"><span class="tiny-cross" aria-hidden="true">✳</span> A DEVELOPER'S WORK IN PROGRESS</p>
          <h1 id="hero-title">Ideas into code.<br />Code into <span class="hero-highlight">reality<svg viewBox="0 0 500 30" aria-hidden="true"><path d="M5 22 Q230 -7 490 13" /></svg></span><span class="text-accent">.</span></h1>
          <div class="hero-bottom mt-10 flex flex-col items-start gap-8 lg:flex-row lg:items-end lg:gap-10">
            <p class="max-w-sm text-base leading-7 text-muted">Hey, I'm <span class="text-ink">{{ profile.name }}</span>. I build for the web, tinker with the cloud, and automate the things that get in the way.</p>
            <a href="#work" class="primary-button shrink-0">Explore the work <span aria-hidden="true">↓</span></a>
          </div>
        </div>
        <div class="hero-art" aria-hidden="true">
          <div class="orbit orbit-one"></div><div class="orbit orbit-two"></div>
          <div class="art-cross cross-one">+</div><div class="art-cross cross-two">+</div>
          <div class="art-label label-top">BUILD SOMETHING THAT MATTERS</div>
          <div class="core-platform platform-bottom"></div><div class="core-platform platform-middle"></div>
          <div class="core-platform platform-top"><span>ag<span class="text-accent">.</span></span></div>
          <div class="art-chip chip-one"><span class="chip-symbol">{ }</span> infrastructure as code</div>
          <div class="art-chip chip-two"><span class="chip-symbol">⌘</span> always learning</div>
          <div class="art-label label-bottom">IDEA · BUILD · SHIP · REPEAT</div>
          <div class="art-coordinate">DESIGNED TO KEEP EVOLVING</div>
        </div>
        <div class="hero-foot flex items-center justify-between gap-4">
          <span class="font-mono text-xs tracking-wider text-muted">CURIOUS BY DEFAULT. BUILDER BY CHOICE.</span>
          <a href="#work" class="scroll-hint hidden items-center gap-3 sm:flex">SCROLL TO EXPLORE <span aria-hidden="true">↓</span></a>
        </div>
      </section>

      <div class="stack-strip" aria-label="Technologies used in this portfolio">
        <div class="page-width flex flex-wrap items-center justify-between gap-x-8 gap-y-5 py-7">
          <span class="font-mono text-xs tracking-widest text-muted">A FEW TOOLS IN THE TOOLBOX</span>
          <div class="flex flex-wrap items-center gap-x-8 gap-y-3 text-sm font-medium text-soft sm:gap-x-10"><span>Amazon Web Services</span><span>Terraform</span><span>Vue.js</span><span>GitHub Actions</span><span>Cloudflare</span></div>
        </div>
      </div>

      <section id="work" class="page-width section-space" aria-labelledby="work-title">
        <div class="flex flex-col justify-between gap-7 md:flex-row md:items-end">
          <div><p class="eyebrow mb-5">THE WORK</p><h2 id="work-title">Small details.<br /><span class="text-muted">Solid foundations.</span></h2></div>
          <p class="max-w-xs text-sm leading-7 text-muted">One portfolio. Three sides of the build.<br />Here's a look under the hood.</p>
        </div>
        <div class="mt-10 flex flex-wrap gap-2" role="group" aria-label="Filter projects">
          <button v-for="filter in filters" :key="filter" class="filter-button" :class="{ selected: activeFilter === filter }" :aria-pressed="activeFilter === filter" @click="activeFilter = filter">{{ filter }}<span v-if="filter === 'All'" class="ml-2 opacity-60">03</span></button>
        </div>
        <div class="projects-grid mt-7 grid gap-6 md:grid-cols-3" aria-live="polite">
          <a v-for="project in visibleProjects" :key="project.title" :href="profile.repository + project.path" class="project-card group">
            <div class="project-art" :class="'project-' + project.visual" aria-hidden="true">
              <template v-if="project.visual === 'cloud'"><div class="cloud-network"><span class="network-end">DNS</span><i></i><span class="network-core">EDGE</span><i></i><span class="network-end">S3</span></div><span class="preview-caption">PRIVATE ORIGIN. GLOBAL REACH.</span></template>
              <template v-else-if="project.visual === 'pipeline'"><div class="pipeline-window"><div class="window-dots"><i></i><i></i><i></i><span>deploy.yml</span></div><div class="pipeline-line"><span>✓</span> validate <small>passed</small></div><div class="pipeline-line"><span>✓</span> build <small>passed</small></div><div class="pipeline-line"><span>✓</span> deploy <small>live</small></div></div></template>
              <template v-else><div class="mini-browser"><div class="window-dots"><i></i><i></i><i></i><span>angelgp.dev</span></div><div class="mini-content"><b>Ideas into code.<br /><em>Code into reality.</em></b><span></span><span></span><div>Explore the work</div></div></div></template>
              <span class="project-open">↗</span>
            </div>
            <div class="p-6"><p class="font-mono text-xs tracking-widest text-muted">{{ project.label }}</p><h3 class="mt-3 text-xl font-semibold tracking-tight">{{ project.title }}</h3><p class="mt-3 text-sm leading-6 text-muted">{{ project.description }}</p><ul class="mt-6 flex flex-wrap gap-2"><li v-for="tag in project.tags" :key="tag" class="tag">{{ tag }}</li></ul></div>
          </a>
        </div>
        <a :href="profile.repository" class="text-link mt-8 inline-flex items-center gap-3">All the code, out in the open <span aria-hidden="true">↗</span></a>
      </section>

      <section id="about" class="about-section section-space" aria-labelledby="about-title">
        <div class="page-width grid items-start gap-14 lg:grid-cols-2 lg:gap-20">
          <div><p class="eyebrow mb-5">THE PERSON BEHIND THE COMMITS</p><h2 id="about-title">A curious mind.<br /><span class="text-muted">A builder's instinct.</span></h2><p class="mt-7 max-w-lg leading-8 text-muted">I'm Angel, a developer who enjoys connecting the dots between a thoughtful interface and the infrastructure that keeps it running.</p><p class="mt-4 max-w-lg leading-8 text-muted">I learn by building, breaking things, and figuring out why. This portfolio is part introduction, part playground, and an ongoing record of that process.</p><div class="mt-8 flex items-center gap-4"><span class="signature">Angel.</span><span class="h-8 w-px bg-line"></span><span class="font-mono text-xs leading-5 text-muted">LESS FRICTION.<br />MORE MAKING.</span></div></div>
          <div class="terminal">
            <div class="terminal-title flex items-center justify-between"><div class="window-dots"><i></i><i></i><i></i></div><span>meet-angel.sh</span><span aria-hidden="true">⌘</span></div>
            <div ref="terminalBody" class="terminal-body"><div v-for="(entry, index) in terminalHistory" :key="index" class="mb-5"><p class="terminal-command"><span>visitor@portfolio</span><span class="text-muted">:~$</span> {{ entry.command }}</p><p class="terminal-output">{{ entry.output }}</p></div><form @submit.prevent="runCommand()" class="flex items-center gap-2"><label for="terminal-command" class="shrink-0 text-accent"><span class="sr-only">Terminal command</span><span aria-hidden="true">~ $</span></label><input id="terminal-command" v-model="terminalInput" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="160" placeholder="type help, then press enter" class="min-w-0 flex-1 bg-transparent text-ink outline-none" /><button class="terminal-submit" type="submit" aria-label="Run command">↵</button></form></div>
            <div class="terminal-footer flex flex-wrap items-center gap-3"><span>Try:</span><button v-for="command in ['help', 'stack', 'hello']" :key="command" @click="runCommand(command)">{{ command }}</button><span class="ml-auto text-muted">interactive terminal</span></div>
          </div>
        </div>
      </section>

      <section class="page-width section-space" aria-labelledby="approach-title"><div class="flex flex-col justify-between gap-5 md:flex-row md:items-end"><div><p class="eyebrow mb-5">HOW I LIKE TO BUILD</p><h2 id="approach-title">The right tools.<br /><span class="text-muted">A little intention.</span></h2></div><p class="max-w-xs text-sm leading-7 text-muted">Always exploring. Always refining.<br />These are a few things I keep coming back to.</p></div><div class="mt-12 grid gap-8 md:grid-cols-3"><article v-for="skill in skills" :key="skill.title" class="skill-card"><div class="skill-icon" aria-hidden="true"><svg v-if="skill.icon === 'layers'" viewBox="0 0 32 32"><path d="m4 10 12-7 12 7-12 7zM4 16l12 7 12-7M4 22l12 7 12-7" /></svg><svg v-else-if="skill.icon === 'flow'" viewBox="0 0 32 32"><rect x="3" y="4" width="9" height="9" rx="2" /><rect x="20" y="19" width="9" height="9" rx="2" /><path d="M12 8h7a6 6 0 0 1 6 6v5M7 13v15m-4-4 4 4 4-4" /></svg><svg v-else viewBox="0 0 32 32"><rect x="3" y="5" width="26" height="23" rx="3" /><path d="M3 12h26M8 9h1m4 0h1m-5 8 4 3-4 3m8 0h6" /></svg></div><h3 class="mt-6 text-lg font-semibold">{{ skill.title }}</h3><p class="mt-3 text-sm leading-7 text-muted">{{ skill.description }}</p><p class="mt-6 border-t border-line pt-5 font-mono text-xs leading-6 text-soft">{{ skill.tools }}</p></article></div></section>

      <section id="contact" class="contact-section" aria-labelledby="contact-title"><div class="page-width relative py-20 md:py-28"><div class="contact-asterisk" aria-hidden="true">✳</div><p class="eyebrow mb-6">GOOD THINGS START WITH A CONVERSATION</p><h2 id="contact-title">Have something<br />in mind<span class="text-accent">?</span></h2><div class="relative z-10 mt-8 flex flex-col items-start justify-between gap-8 sm:flex-row sm:items-center"><p class="max-w-md leading-7 text-muted">An idea, a question, or just a shared curiosity.<br />I'd love to hear about it.</p><a :href="profile.github" class="primary-button">Let's connect on GitHub <span aria-hidden="true">↗</span></a></div></div></section>
    </main>

    <footer class="page-width flex flex-col justify-between gap-5 py-7 text-xs text-muted sm:flex-row sm:items-center"><a href="#" class="wordmark" aria-label="Back to top">ag<span class="text-accent">.</span></a><span>© {{ new Date().getFullYear() }} {{ profile.name }}. Built with intention, shipped with curiosity.</span><a href="#" class="text-link">Back to top ↑</a></footer>
  </div>
</template>
