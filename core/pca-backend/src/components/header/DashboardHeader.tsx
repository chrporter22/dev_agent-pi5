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

      <div
        className="
        text-viridis-600
        font-bold
        text-5xl
        leading-none
        mb-2
        tracking-[0.3em]
        select-none
        "
      >
        PCA
      </div>

      <h1
        className="
        text-sm
        font-normal
        mb-4
        text-muted
        tracking-widest
        uppercase
        "
      >
        Dev Agent Pi5 Dashboard
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
