import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Rare ports on purpose: the dev machines run many containers/servers, so the
// dev server (43212) and the local backend it proxies to (43211) stay out of
// the common 5173/8000 range. Inside docker the nginx proxy is used instead.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 43212,
    proxy: {
      "/api": "http://localhost:43211",
    },
  },
});
