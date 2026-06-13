import Card from "../ui/Card"

interface Props {
  heartbeat?: number
  lastRun?: number
}

export default function WorkerCard({
  heartbeat,
  lastRun
}: Props) {

  const alive =
    heartbeat
      ? Date.now() / 1000 - heartbeat < 30
      : false

  return (
    <Card title="Worker">

      <div
        className="
        text-2xl
        font-bold
        "
      >
        {alive
          ? "Healthy"
          : "Offline"}
      </div>

      <div
        className="
        text-muted
        mt-3
        "
      >
        Last Run: {lastRun}
      </div>

    </Card>
  )
}
