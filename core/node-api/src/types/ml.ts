export interface PcaSummary {
  projection: number[][]
  components: number[][]
  variance: number[]
  eigenvalues: number[]
  totalVariance: number
  mean: number[]
  std: number[]
  drift: number
  risk: string
  confidence: number
}
