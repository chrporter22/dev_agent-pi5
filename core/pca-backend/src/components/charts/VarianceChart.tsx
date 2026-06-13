import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip
} from "recharts"

import Card from "../ui/Card"

interface Props {
  variance: number[]
}

export default function VarianceChart({
  variance
}: Props) {

  const data =
    variance.map(
      (value, index) => ({
        pc: `PC${index + 1}`,
        variance: value
      })
    )

  return (
    <Card title="Variance">

      <ResponsiveContainer
        width="100%"
        height={300}
      >
        <BarChart data={data}>

          <XAxis dataKey="pc" />

          <YAxis />

          <Tooltip />

          <Bar
            dataKey="variance"
            fill="#6CCE59"
          />

        </BarChart>
      </ResponsiveContainer>

    </Card>
  )
}
