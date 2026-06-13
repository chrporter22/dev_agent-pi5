import Card from "../ui/Card"

interface Props {
  drift: number
  classification?: string
}

export default function DriftCard({
  drift,
  classification
}: Props) {
  return (
    <Card title="Drift">

      <div
        className="
        text-4xl
        font-bold
        text-viridis-700
        "
      >
        {drift.toFixed(3)}
      </div>

      <div
        className="
        text-muted
        mt-2
        "
      >
        {classification ?? "Unknown"}
      </div>

    </Card>
  )
}
