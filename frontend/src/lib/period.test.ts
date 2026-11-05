import { describe, expect, it } from "vitest"

import { periodParams } from "@/lib/period"

describe("periodParams", () => {
  it("anchors the window on the dataset end date", () => {
    expect(periodParams("30d", "2023-01-01", "2023-07-20")).toEqual({
      date_from: "2023-06-20",
      date_to: "2023-07-20",
    })
  })

  it("does not start before the dataset", () => {
    expect(periodParams("12m", "2023-06-01", "2023-07-20").date_from).toBe("2023-06-01")
  })

  it("returns the full span for all dates", () => {
    expect(periodParams("all", "2023-01-01", "2023-07-20")).toEqual({
      date_from: "2023-01-01",
      date_to: "2023-07-20",
    })
  })
})
