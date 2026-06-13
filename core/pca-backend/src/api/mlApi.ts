import axios from "axios"

import {
  PcaSummary,
  HistoryPoint
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

export default api
