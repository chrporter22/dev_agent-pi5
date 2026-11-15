import { useQuery } from "@tanstack/react-query"

import { getSessions } from "../api/mlApi"

export function useSessions() {
  return useQuery({
    queryKey: ["sessions"],
    queryFn: getSessions,
    refetchInterval: 15000,
    staleTime: 12000
  })
}
