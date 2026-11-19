<template>
  <div class="min-h-screen bg-base text-ink">
    <a href="#workspace-main" class="skip-link">Skip to content</a>
    <header class="border-b border-line">
      <div class="page-width flex items-center justify-between gap-5 py-6">
        <RouterLink to="/" class="wordmark" aria-label="Back to portfolio">ag<span class="text-accent">.</span></RouterLink>
        <div class="flex items-center gap-6 text-sm"><RouterLink to="/" class="nav-link">Portfolio</RouterLink><slot name="actions" /></div>
      </div>
    </header>
    <main id="workspace-main" class="page-width py-14 md:py-24"><slot /></main>
  </div>
</template>
