<template>
  <a href="#main" class="skip-link">Skip to content</a>
  <header class="site-header">
    <div class="page-width flex flex-wrap items-center justify-between gap-x-6 gap-y-4 py-5">
      <RouterLink to="/" class="wordmark" aria-label="Angel portfolio home">ag<span class="text-accent">.</span></RouterLink>
      <nav class="flex flex-wrap items-center gap-x-5 gap-y-2" aria-label="Main navigation">
        <RouterLink to="/" class="nav-link">Home</RouterLink>
        <RouterLink to="/projects" class="nav-link">Projects</RouterLink>
        <RouterLink to="/about" class="nav-link">About</RouterLink>
        <RouterLink to="/tools" class="nav-link">Tools</RouterLink>
      </nav>
    </div>
  </header>
  <main id="main" tabindex="-1" class="page-width section-space">
    <slot />
  </main>
</template>
