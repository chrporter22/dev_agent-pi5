import Card from "../ui/Card"

interface Props {
  totalVariance: number
}

export default function VarianceSummaryCard({
  totalVariance
}: Props) {

  const percent =
    totalVariance * 100

  let status = "Poor"
  let color = "text-red-400"

  if (percent >= 90) {
    status = "Excellent"
    color = "text-viridis-800"
  } else if (percent >= 75) {
    status = "Good"
    color = "text-viridis-700"
  } else if (percent >= 50) {
    status = "Moderate"
    color = "text-yellow-400"
  }

  return (
    <Card title="Explained Variance">

      <div
        className={`
          text-4xl
          font-bold
          ${color}
        `}
      >
        {percent.toFixed(1)}%
      </div>

      <div
        className="
        mt-2
        text-sm
        text-muted
        "
      >
        Total PCA variance retained
      </div>

      <div
        className="
        mt-4
        flex
        items-center
        justify-between
        "
      >
        <span
          className="
          text-xs
          uppercase
          tracking-wider
          text-muted
          "
        >
          Quality
        </span>

        <span
          className={`
            text-sm
            font-semibold
            ${color}
          `}
        >
          {status}
        </span>
      </div>

      <div
        className="
        mt-4
        h-2
        w-full
        rounded-full
        bg-background
        overflow-hidden
        "
      >
        <div
          className="
          h-full
          rounded-full
          bg-gradient-to-r
          from-viridis-50
          via-viridis-500
          to-viridis-900
          "
          style={{
            width: `${Math.min(percent, 100)}%`
          }}
        />
      </div>

    </Card>
  )
}
