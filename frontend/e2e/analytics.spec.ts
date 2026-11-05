import { expect, test } from "@playwright/test"

test("a new account can clean the sample and see calculated revenue", async ({ page }) => {
  const email = `ada.${Date.now()}@example.com`
  await page.goto("/register")
  await page.getByLabel("Full name").fill("Ada Lovelace")
  await page.getByLabel("Email").fill(email)
  await page.getByLabel("Password").fill("password123")
  await page.getByRole("button", { name: "Create account" }).click()
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible()

  await page.getByRole("link", { name: "Data Management" }).click()
  await page.getByRole("button", { name: "Load sample transactions" }).click()
  await expect(page.getByRole("heading", { name: "Sample retail transactions" })).toBeVisible()
  const clean = page.getByRole("button", { name: "Create cleaned version" })
  await expect(clean).toBeEnabled()
  await clean.click()
  await expect(page.getByText("Cleaned version created.")).toBeVisible()
  await expect(page.getByRole("button", { name: "Cleaned", exact: true })).toBeEnabled()

  await page.getByRole("link", { name: "Overview" }).click()
  await expect(page.getByText("Revenue", { exact: true })).toBeVisible()
  await expect(page.getByText("Generated sample, not the UCI Online Retail II extract.")).toBeVisible()
})
