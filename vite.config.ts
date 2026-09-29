import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  root: "apps/web",
  plugins: [react()],
  build: { outDir: "../../dist", emptyOutDir: true },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/media": "http://127.0.0.1:8765",
      "/screen-ingest": "http://127.0.0.1:8765",
    },
  },
});
