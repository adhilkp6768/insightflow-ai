import { describe, expect, it } from "vitest"

import { applyTheme, getStoredTheme } from "@/lib/theme"

describe("theme", () => {
  it("defaults to light and stores the dark choice", () => {
    localStorage.clear()
    document.documentElement.classList.remove("dark")

    expect(getStoredTheme()).toBe("light")
    applyTheme("dark")

    expect(document.documentElement.classList.contains("dark")).toBe(true)
    expect(getStoredTheme()).toBe("dark")
  })
})
