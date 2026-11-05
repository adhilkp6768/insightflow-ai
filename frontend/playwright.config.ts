import { defineConfig, devices } from "@playwright/test"

const secret = process.env.JWT_SECRET ?? "local-development-secret-not-for-production-use"
const database = process.env.DATABASE_URL ?? "sqlite+pysqlite:///./e2e.db"
const python = process.env.CI ? "python" : ".venv/bin/python"

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: {
    ...devices["Desktop Chrome"],
    baseURL: "http://127.0.0.1:5173",
  },
  webServer: [
    {
      command: `cd ../backend && JWT_SECRET="${secret}" DATABASE_URL="${database}" REDIS_URL="" RATE_LIMIT_ENABLED=false ${python} -m uvicorn app.main:app --host 127.0.0.1 --port 8000`,
      url: "http://127.0.0.1:8000/api/v1/health",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5173",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
})
