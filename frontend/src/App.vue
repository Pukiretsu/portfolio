<script setup>
// Edit these details to make the page your own.
const profile = {
  name: 'Angel',
  role: 'Developer & cloud enthusiast',
  github: 'https://github.com/Pukiretsu',
}
const interests = ['Cloud infrastructure', 'DevOps & automation', 'Web development']
</script>

<template>
  <div class="page">
    <a class="skip-link" href="#main">Skip to content</a>
    <header class="header">
      <a class="wordmark" href="/" aria-label="Portfolio home">angel<span>.dev</span></a>
      <a class="nav-link" :href="profile.github">GitHub</a>
    </header>

    <main id="main">
      <section class="welcome" aria-labelledby="welcome-title">
        <p class="eyebrow">{{ profile.role }}</p>
        <h1 id="welcome-title">Hi, I'm {{ profile.name }}.<br /><span>Welcome to my corner<br class="desktop-break" /> of the internet.</span></h1>
        <p class="intro">I enjoy building software, exploring the cloud, and making things work better through automation. This is where I'll share what I'm working on and learning along the way.</p>
        <a class="button" :href="profile.github">Explore my GitHub</a>
      </section>

      <section class="interests" aria-labelledby="interests-title">
        <h2 id="interests-title">Things I like working on</h2>
        <ul>
          <li v-for="interest in interests" :key="interest">{{ interest }}</li>
        </ul>
      </section>

      <aside class="note">
        <span class="note-label">A work in progress</span>
        <p>The foundation is here. Projects, stories, and a little more about me are coming next.</p>
      </aside>
    </main>

    <footer>
      <span>© {{ new Date().getFullYear() }} {{ profile.name }}</span>
      <span>Built with curiosity.</span>
    </footer>
  </div>
</template>
