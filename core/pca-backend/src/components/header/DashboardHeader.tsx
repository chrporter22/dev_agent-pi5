import Badge from "../ui/Badge"

interface Props {
  heartbeat?: number
  lastRun?: number
  drift: number
}

export default function DashboardHeader({
  heartbeat,
  lastRun,
  drift
}: Props) {
  const alive =
    heartbeat
      ? Date.now() / 1000 - heartbeat < 30
      : false

  return (
    <header className="mb-8">

      <pre
        className="
        text-viridis-600
        text-xs
        mb-4
        "
      >
{`
 ██████╗  ██████╗ █████╗
 ██╔══██╗██╔════╝██╔══██╗
 ██████╔╝██║     ███████║
 ██╔═══╝ ██║     ██╔══██║
 ██║     ╚██████╗██║  ██║
`}
      </pre>

      <h1
        className="
        text-3xl
        font-bold
        mb-4
        "
      >
        OpenClaw PCA Monitoring
      </h1>

      <div className="flex gap-3">

        <Badge
          label={
            alive
              ? "ML ONLINE"
              : "OFFLINE"
          }
          color={
            alive
              ? "bg-viridis-700"
              : "bg-red-500"
          }
        />

        <Badge
          label={`Drift ${drift.toFixed(3)}`}
        />

        <Badge
          label={`Run ${lastRun ?? "-"}`}
        />

      </div>

    </header>
  )
}
