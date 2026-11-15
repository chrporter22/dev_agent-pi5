export interface PcaSummary {

  projection: number[][]

  components: number[][]

  variance: number[]

  eigenvalues: number[]

  totalVariance: number

  mean: number[]

  std: number[]

  drift: number

  driftClassification?: string

  risk?: string

  confidence?: number

  heartbeat?: number

  lastRun?: number
}

export interface HistoryPoint {

  timestamp?: number

  projection: number[][]

  drift?: number

  risk?: string
}

export interface Session {
  id: string
  status: string
  type: string
  step: string | null
  createdAt: number | null
  updatedAt: number | null
  result: string | null
  error: string | null
  prUrl: string | null
  chatId: string | null
  feature: string | null
  text: string | null
}
