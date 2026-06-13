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

interface Props {
  history: HistoryPoint[]
}

export default function HistoryTimeline({
  history
}: Props) {

  const data =
    history.map(
      (item, index) => ({
        index,
        value:
          item.projection?.length ?? 0
      })
    )

  return (
    <Card title="History Timeline">

      <ResponsiveContainer
        width="100%"
        height={300}
      >
        <LineChart data={data}>

          <XAxis dataKey="index" />

          <YAxis />

          <Tooltip />

          <Line
            type="monotone"
            dataKey="value"
            stroke="#35B779"
          />

        </LineChart>
      </ResponsiveContainer>

    </Card>
  )
}
