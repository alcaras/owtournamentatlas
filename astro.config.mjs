import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://alcaras.github.io',
  base: '/owtournamentatlas/',
  build: { format: 'directory' },
  trailingSlash: 'ignore',
});
