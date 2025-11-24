import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const apiTarget =
    env.VITE_API_BASE_URL ||
    env.VITE_DEPLOY_BACKEND_URL ||
    "http://127.0.0.1:8010";

  return {
    plugins: [react()],
    server: {
      port: Number(env.VITE_DEV_PORT ?? 5173),
      host: env.VITE_DEV_HOST ?? "127.0.0.1",
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
          ws: true,
        },
        "/tracer": {
          target: apiTarget,
          changeOrigin: true,
          ws: true,
        },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: true,
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./src/setupTests.ts"],
      css: true,
    },
  };
});
