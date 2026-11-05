import { QueryClient } from "@tanstack/react-query"

import { ApiError } from "@/services/api"

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError && [401, 403, 404].includes(error.status)) return false
        return failureCount < 1
      },
    },
  },
})
