import Badge from "../ui/Badge"
import { PCA_ASCII } from "./pcaAscii"

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
          font-mono
          text-viridis-600
          text-lg
          md:text-xl
          xl:text-2xl
          leading-none
          mb-2
          select-none
          overflow-x-auto
        "
      >
        {PCA_ASCII}
      </pre>

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
