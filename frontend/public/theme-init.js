(() => {
  let theme
  try { theme = localStorage.getItem('portfolio-theme') } catch { /* Storage is optional. */ }

  if (theme !== 'dark' && theme !== 'light') {
    theme = matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
  }
  document.documentElement.dataset.theme = theme
})()
