import { useMemo, useState } from "react"

import {
  ScatterChart,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
  ResponsiveContainer,
  CartesianGrid
} from "recharts"

import Card from "../ui/Card"
import Select from "../ui/Select"

interface Props {
  projection: number[][]
}

export default function PCAExplorer({
  projection
}: Props) {

  const dimensions =
    projection?.[0]?.length ?? 2

  const [xAxis, setXAxis] =
    useState(0)

  const [yAxis, setYAxis] =
    useState(1)

  const options =
    Array.from(
      { length: dimensions },
      (_, i) => `PC${i + 1}`
    )

  const points = useMemo(
    () =>
      projection.map(
        (row, index) => ({
          id: index,
          x: row[xAxis],
          y: row[yAxis]
        })
      ),
    [projection, xAxis, yAxis]
  )

  return (
    <Card title="PCA Explorer">

      <div
        className="
        flex
        gap-4
        mb-4
        "
      >
        <Select
          value={xAxis}
          options={options}
          onChange={setXAxis}
        />

        <Select
          value={yAxis}
          options={options}
          onChange={setYAxis}
        />
      </div>

      <ResponsiveContainer
        width="100%"
        height={500}
      >
        <ScatterChart>

          <CartesianGrid />

          <XAxis dataKey="x" />

          <YAxis dataKey="y" />

          <Tooltip />

          <Scatter
            data={points}
            fill="#35B779"
          />

        </ScatterChart>
      </ResponsiveContainer>

    </Card>
  )
}
