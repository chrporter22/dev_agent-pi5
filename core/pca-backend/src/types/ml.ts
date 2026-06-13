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

  risk: string

  confidence: number

  heartbeat?: number

  lastRun?: number
}

export interface HistoryPoint {

  timestamp?: number

  projection: number[][]

  drift?: number

  risk?: string
}
