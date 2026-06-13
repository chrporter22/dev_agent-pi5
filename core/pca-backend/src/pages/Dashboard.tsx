import DashboardLayout from "../layouts/DashboardLayout"

import { usePcaSummary } from "../hooks/usePcaSummary"
import { usePcaHistory } from "../hooks/usePcaHistory"

import DashboardHeader from "../components/header/DashboardHeader"

import DriftCard from "../components/cards/DriftCard"
import RiskCard from "../components/cards/RiskCard"
import WorkerCard from "../components/cards/WorkerCard"
import VarianceSummaryCard from "../components/cards/VarianceSummaryCard"

import PCAExplorer from "../components/charts/PCAExplorer"
import VarianceChart from "../components/charts/VarianceChart"
import EigenvalueChart from "../components/charts/EigenvalueChart"
import HistoryTimeline from "../components/charts/HistoryTimeline"

export default function Dashboard() {

  const {
    data,
    isLoading,
    error
  } = usePcaSummary()

  const {
    data: history
  } = usePcaHistory()

  if (isLoading) {
    return (
      <DashboardLayout>
        <div
          className="
            flex
            items-center
            justify-center
            h-[80vh]
            text-viridis-700
            text-xl
          "
        >
          Loading PCA Dashboard...
        </div>
      </DashboardLayout>
    )
  }

  if (error || !data) {
    return (
      <DashboardLayout>
        <div
          className="
            p-6
            border
            border-red-500
            rounded-lg
            text-red-400
          "
        >
          Failed to load dashboard
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout>

      {/* HEADER */}
      <DashboardHeader
        heartbeat={data.heartbeat}
        lastRun={data.lastRun}
        drift={data.drift}
      />

      {/* KPI ROW */}
      <div
        className="
          grid
          grid-cols-1
          md:grid-cols-4
          gap-4
          mb-6
        "
      >

        <DriftCard
          drift={data.drift}
          classification={data.driftClassification}
        />

        <RiskCard
          risk={data.risk}
          confidence={data.confidence}
        />

        <VarianceSummaryCard
          totalVariance={data.totalVariance}
        />

        <WorkerCard
          heartbeat={data.heartbeat}
          lastRun={data.lastRun}
        />

      </div>

      {/* PCA EXPLORER */}
      <section className="mb-6">
        <PCAExplorer
          projection={data.projection}
        />
      </section>

      {/* CHART GRID */}
      <section
        className="
          grid
          grid-cols-1
          xl:grid-cols-2
          gap-6
          mb-6
        "
      >

        <VarianceChart
          variance={data.variance}
        />

        <EigenvalueChart
          eigenvalues={data.eigenvalues}
        />

      </section>

      {/* HISTORY */}
      <section>
        <HistoryTimeline
          history={history ?? []}
        />
      </section>

    </DashboardLayout>
  )
}
