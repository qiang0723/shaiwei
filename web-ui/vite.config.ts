import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  build: {
    target: "es2022",
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("@ant-design/charts") || id.includes("@antv/")) {
            return "vendor-charts";
          }
          if (id.includes("@tanstack/react-query")) return "vendor-query";
          if (id.includes("antd") || id.includes("@ant-design/icons")) {
            return "vendor-antd";
          }
          if (
            id.includes("/react/") ||
            id.includes("/react-dom/")
          ) {
            return "vendor-react";
          }
          return undefined;
        }
      }
    }
  },
  test: {
    include: ["src/test/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
    coverage: {
      reporter: ["text", "json-summary"]
    }
  }
});
