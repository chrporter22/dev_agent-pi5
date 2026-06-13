import { useQuery }
from "@tanstack/react-query"

import {
  getHistory
}
from "../api/mlApi"

export function usePcaHistory() {

  return useQuery({

    queryKey: [
      "pca-history"
    ],

    queryFn: getHistory,

    refetchInterval: 10000,

    staleTime: 8000
  })
}
