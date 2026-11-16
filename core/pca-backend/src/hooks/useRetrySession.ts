// core/pca-backend/src/hooks/useRetrySession.ts
// ----------------------------------------------------------------------------
// TanStack Query mutation hook for retrying a failed job.  On success the
// sessions list is invalidated so the row reflects the new `queued` status.
// ----------------------------------------------------------------------------

import {
  useMutation,
  useQueryClient
} from "@tanstack/react-query"

import { retrySession } from "../api/mlApi"

export function useRetrySession() {

  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: retrySession,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["sessions"]
      })
    }
  })
}
