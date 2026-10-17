import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiProxyTarget = process.env.PAPER_VAULT_API_PROXY || "http://127.0.0.1:8020";

export default defineConfig({
  plugins: [react()],
  build: {
    // The SPA ships inside the Python package so `uv tool install paperpilot` can
    // serve the page without Node (see src/paperpilot/webapp.py). The directory is
    // generated: never edit it by hand, rebuild with `npm run build`.
    outDir: "../src/paperpilot/web",
    emptyOutDir: true
  },
  server: {
    proxy: {
      "/api": apiProxyTarget
    }
  }
});
