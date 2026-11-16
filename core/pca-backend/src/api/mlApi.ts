import axios from "axios"

import {
  PcaSummary,
  HistoryPoint,
  Session
} from "../types/ml"

const api = axios.create({

  baseURL: "/api/ml",

  timeout: 10000
})

export async function getSummary() {

  const { data } =
    await api.get<PcaSummary>(
      "/pca/summary"
    )

  return data
}

export async function getHistory() {

  const { data } =
    await api.get<HistoryPoint[]>(
      "/pca/history"
    )

  return data
}

export async function getSessions() {

  const { data } =
    await api.get<{ sessions: Session[] }>(
      "/sessions"
    )

  return data.sessions
}

export async function retrySession(jobId: string) {

  const { data } =
    await api.post<{ ok: boolean; jobId: string; requeuedAt: number }>(
      `/sessions/${jobId}/retry`
    )

  return data
}

export default api
