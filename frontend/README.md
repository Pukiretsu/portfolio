# Portfolio frontend

Vue, Vite, and Tailwind CSS v4. Use Node.js 24 LTS.

```sh
npm ci
npm run dev
```

## Portfolio content

- Add a Markdown file to `src/content/projects/` for each write-up. The lowercase, hyphenated filename becomes the URL. For example, `my-project.md` appears at `/projects/my-project`.
- Start each file with a `# Project title` heading and a short plain-text paragraph for the blog index. Then add the full write-up with Markdown headings, lists, links, images, or fenced code blocks.
- Edit `src/content/about.md` for the About page and `src/content/profile.js` for social links.
- Edit `src/views/PortfolioView.vue` for the homepage’s featured project cards and stack. Rebuild and deploy the frontend to publish changes.

Vue Router is configured in `src/router.js`. `src/App.vue` renders the router and handles expired sessions. Cognito integration lives in `src/auth/cognito.js`; the login, OAuth callback, and Tools pages are separate components in `src/views/`. The public `/auth-config.json` runtime settings are created by Terraform. See the root README for invitations and security boundaries.

```sh
npm run build
npm run preview
```

The production site is generated in `dist/`. Never place secrets in frontend code or `VITE_*` variables: they are visible to visitors.
