import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    watch: {
      // Exclude venv and large non-frontend directories from file watching
      ignored: [
        "**/node_modules/**",
        "**/.venv311/**",
        "**/ml/.venv311/**",
        "**/backend/.venv311/**",
        "**/catboost_info/**",
        "**/validation_reports/**",
        "**/artifacts/**",
        "**/__pycache__/**",
        "**/*.pyc",
      ],
    },
  },
});
