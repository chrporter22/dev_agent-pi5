import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip
} from "recharts"

import Card from "../ui/Card"

import {
  HistoryPoint
} from "../../types/ml"

function centroidL2Norm(projection: number[][]): number {
  if (!projection || projection.length < 1) return 0
  const numPCs = projection[0].length
  const centroid = new Array(numPCs).fill(0)
  for (const sample of projection) {
    for (let j = 0; j < numPCs; j++) {
      centroid[j] += sample[j]
    }
  }
  const n = projection.length
  let sq = 0
  for (let j = 0; j < numPCs; j++) {
    const c = centroid[j] / n
    sq += c * c
  }
  return Math.sqrt(sq)
}

interface Props {
  history: HistoryPoint[]
}

export default function HistoryTimeline({
  history
}: Props) {

  const data =
    history.map((item, index) => {
      const norm = centroidL2Norm(item.projection)
      const ts = item.timestamp
        ? new Date(item.timestamp * 1000)
        : null
      return {
        index,
        norm: parseFloat(norm.toFixed(4)),
        time: ts
          ? ts.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
          : `T-${history.length - 1 - index}`
      }
    })

  return (
    <Card title="Centroid Distance History">

      <ResponsiveContainer
        width="100%"
        height={300}
      >
        <LineChart data={data}>
          <XAxis
            dataKey="time"
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            axisLine={{ stroke: "#1f2937" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            axisLine={{ stroke: "#1f2937" }}
            tickLine={false}
            tickFormatter={v => v.toFixed(2)}
          />
          <Tooltip
            formatter={(val: number) => [val.toFixed(4), "Centroid L2 norm"]}
            labelStyle={{ color: "#e5e7eb" }}
            contentStyle={{
              background: "#111827",
              border: "1px solid #1f2937",
              borderRadius: 8
            }}
          />
          <Line
            type="monotone"
            dataKey="norm"
            stroke="#35B779"
            dot={false}
            strokeWidth={1.5}
          />
        </LineChart>
      </ResponsiveContainer>

    </Card>
  )
}
