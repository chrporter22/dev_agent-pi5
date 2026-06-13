import { useQuery }
from "@tanstack/react-query"

import {
  getSummary
}
from "../api/mlApi"

export function usePcaSummary() {

  return useQuery({

    queryKey: [
      "pca-summary"
    ],

    queryFn: getSummary,

    refetchInterval: 5000,

    staleTime: 4000
  })
}
