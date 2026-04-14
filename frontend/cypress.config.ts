import { defineConfig } from "cypress";

export default defineConfig({
  e2e: {
    baseUrl: "http://localhost:5173",
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
    viewportWidth: 1280,
    viewportHeight: 720,
    supportFile: "cypress/support/e2e.ts"
  },
  // Suppress security warning
  env: {
    allowCypressEnv: false
  }
});
