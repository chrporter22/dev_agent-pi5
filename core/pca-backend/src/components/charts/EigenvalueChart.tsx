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
  eigenvalues: number[]
}

export default function EigenvalueChart({
  eigenvalues
}: Props) {

  const data =
    eigenvalues.map(
      (value, index) => ({
        pc: `PC${index + 1}`,
        value
      })
    )

  return (
    <Card title="Eigenvalues">

      <ResponsiveContainer
        width="100%"
        height={300}
      >
        <BarChart data={data}>

          <XAxis dataKey="pc" />

          <YAxis />

          <Tooltip />

          <Bar
            dataKey="value"
            fill="#B4DE2C"
          />

        </BarChart>
      </ResponsiveContainer>

    </Card>
  )
}
