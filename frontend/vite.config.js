import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite needs this config file to enable the React plugin (fast refresh, JSX).
export default defineConfig({
  plugins: [react()],
});