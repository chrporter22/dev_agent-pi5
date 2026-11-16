// core/pca-backend/src/components/charts/LoadingsChart.tsx
// ----------------------------------------------------------------------------
// PCA Feature Contributions — top contributors per top-3 PCs.
// When encodingMap is supplied the chart aggregates squared loadings back to
// the original feature level.  Falls back to per-dimension (Dim N) labels when
// no encoding map is present.  Three PCs render side-by-side at lg+.
// ----------------------------------------------------------------------------

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell
} from "recharts"

import Card from "../ui/Card"

const PC_COLORS = [
  "#35B779",
  "#6CCE59",
  "#B4DE2C"
]

function aggregateByOriginalFeature(
  components: number[][],
  pcIndex: number,
  encodingMap: Record<string, number[]>
): Array<{ name: string; sq: number }> {
  const pcLoadings = components[pcIndex] || []
  const aggregated: Record<string, number> = {}
  for (const [name, indices] of Object.entries(encodingMap)) {
    const sqSum = indices.reduce(
      (sum, idx) => sum + (pcLoadings[idx] || 0) ** 2,
      0
    )
    aggregated[name] = sqSum
  }
  return Object.entries(aggregated)
    .map(([name, sq]) => ({ name, sq }))
    .sort((a, b) => b.sq - a.sq)
}

function topDimsBySq(
  components: number[][],
  pcIndex: number,
  topN: number
): Array<{ name: string; sq: number }> {
  const pcLoadings = components[pcIndex] || []
  return pcLoadings
    .map((loading, idx) => ({ name: `Dim ${idx + 1}`, sq: loading ** 2 }))
    .sort((a, b) => b.sq - a.sq)
    .slice(0, topN)
}

function normalize(values: number[]): number[] {
  const total = values.reduce((s, v) => s + v, 0)
  if (total === 0) return values.map(() => 0)
  return values.map(v => (v / total) * 100)
}

interface ChartDataEntry {
  label: string
  share: number
  raw: number
}

interface PCSectionProps {
  pcIdx: number
  components: number[][]
  variance: number[]
  encodingMap?: Record<string, number[]>
  topN: number
  allFeatureNames?: string[]
}

function PCSection({
  pcIdx,
  components,
  variance,
  encodingMap,
  topN,
  allFeatureNames
}: PCSectionProps) {
  const entries =
    encodingMap
      ? aggregateByOriginalFeature(components, pcIdx, encodingMap)
      : topDimsBySq(components, pcIdx, topN)

  const topEntries = entries.slice(0, topN)
  const normShares = normalize(topEntries.map(e => e.sq))

  const chartData: ChartDataEntry[] = topEntries.map((entry, rank) => ({
    label: entry.name,
    share: normShares[rank],
    raw: entry.sq
  }))

  const barHeight = 22
  const chartHeight = Math.min(chartData.length * barHeight + 48, 260)

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <span
          className="text-xs font-mono font-bold"
          style={{ color: PC_COLORS[pcIdx] }}
        >
          PC{pcIdx + 1}
        </span>
        <span className="text-xs text-muted font-mono">
          {(variance[pcIdx] * 100).toFixed(1)}% var
        </span>
      </div>

      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ left: 0, right: 8, top: 0, bottom: 0 }}
        >
          <XAxis
            type="number"
            domain={[0, 100]}
            tickFormatter={v => `${v.toFixed(0)}%`}
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            axisLine={{ stroke: "#1f2937" }}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={110}
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(val: number) => [`${val.toFixed(1)}%`, "Share"]}
            labelStyle={{ color: "#e5e7eb" }}
            contentStyle={{
              background: "#111827",
              border: "1px solid #1f2937",
              borderRadius: 8
            }}
          />
          <Bar dataKey="share" radius={[0, 3, 3, 0]} isAnimationActive={false}>
            {chartData.map((_, idx) => (
              <Cell
                key={idx}
                fill={PC_COLORS[pcIdx]}
                fillOpacity={1 - idx * 0.07}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

interface Props {
  components: number[][]
  variance: number[]
  encodingMap?: Record<string, number[]>
  featureNames?: string[]
  topN?: number
}

export default function LoadingsChart({
  components,
  variance,
  encodingMap,
  featureNames,
  topN = 8
}: Props) {
  const top3PCs = Math.min(3, components.length)

  return (
    <Card title="Feature Contributions">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {Array.from({ length: top3PCs }).map((_, pcIdx) => (
          <PCSection
            key={pcIdx}
            pcIdx={pcIdx}
            components={components}
            variance={variance}
            encodingMap={encodingMap}
            topN={topN}
            allFeatureNames={featureNames}
          />
        ))}
      </div>
    </Card>
  )
}
