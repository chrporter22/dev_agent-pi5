import Card from "../ui/Card"

interface Props {
  risk?: string
  confidence?: number
}

export default function RiskCard({
  risk,
  confidence
}: Props) {
  return (
    <Card title="Risk">

      <div
        className="
        text-4xl
        font-bold
        "
      >
        {risk ?? "Unknown"}
      </div>

      <div
        className="
        text-muted
        mt-2
        "
      >
        {confidence !== undefined
          ? `${(confidence * 100).toFixed(1)}%`
          : "—"}
      </div>

    </Card>
  )
}
