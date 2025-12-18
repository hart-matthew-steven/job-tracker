import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true, // 👈 exposes on LAN
    allowedHosts: [
      "matts-macbook.local",
    ],
    port: 5173,
  },
});