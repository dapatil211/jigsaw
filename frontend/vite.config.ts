import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: [],
      manifest: {
        name: "Jigsaw Assistant",
        short_name: "Jigsaw",
        theme_color: "#f3f0e8",
        background_color: "#f8f5ee",
        display: "standalone",
        start_url: "/"
      }
    })
  ],
  server: {
    host: true,
    port: 5173
  }
});
