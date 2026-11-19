# Portfolio frontend

Vue, Vite, and Tailwind CSS v4. Use Node.js 24 LTS.

```sh
npm ci
npm run dev
```

Edit the profile, projects, and skills in `src/views/PortfolioView.vue` for content. Tailwind utilities handle layout; theme tokens and custom illustrations live in `src/style.css`. Tailwind is compiled using `@tailwindcss/vite`.

The page includes project filters, mobile navigation, an interactive terminal (`help`, `whoami`, `stack`, `projects`, `hello`, and `clear`), and support for reduced-motion preferences.

Vue Router is configured in `src/router.js`. `src/App.vue` renders the router and handles expired sessions. Cognito integration lives in `src/auth/cognito.js`; the login, OAuth callback, and Tools pages are separate components in `src/views/`. The public `/auth-config.json` runtime settings are created by Terraform. See the root README for invitations and security boundaries.

```sh
npm run build
npm run preview
```

The production site is generated in `dist/`. Never place secrets in frontend code or `VITE_*` variables: they are visible to visitors.
