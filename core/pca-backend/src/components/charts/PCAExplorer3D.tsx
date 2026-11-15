import { useEffect, useRef, useMemo } from "react"

import Plotly, {
  type Camera,
  type Config,
  type Data,
  type Figure,
  type Layout
} from "plotly.js-dist-min"

import Card from "../ui/Card"

interface Props {
  projection: number[][]
  variance?: number[]
  driftClassification?: string
}

const DRIFT_COLORS: Record<string, string> = {
  normal: "#35b779",
  watch: "#fde725",
  high: "#ef4444",
  unknown: "#94a3b8"
}

export default function PCAExplorer3D({
  projection,
  variance = [],
  driftClassification = "unknown"
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const plotRef = useRef<Figure | null>(null)

  const { x, y, z, color } = useMemo(() => {
    const pts = projection.map((row) => ({
      x: row[0] ?? 0,
      y: row[1] ?? 0,
      z: row[2] ?? 0
    }))

    const baseColor = DRIFT_COLORS[driftClassification] || DRIFT_COLORS.unknown

    return {
      x: pts.map((p) => p.x),
      y: pts.map((p) => p.y),
      z: pts.map((p) => p.z),
      color: pts.map(() => baseColor)
    }
  }, [projection, driftClassification])

  const varianceLabels = useMemo(() => {
    const total = variance.reduce((s, v) => s + v, 0) || 1
    return variance.map((v, i) => `PC${i + 1} · ${((v / total) * 100).toFixed(1)}%`)
  }, [variance])

  useEffect(() => {
    if (!containerRef.current) return
    if (!projection || projection.length === 0) return

    const trace: Data = {
      type: "scatter3d",
      mode: "markers",
      x,
      y,
      z,
      marker: {
        color,
        size: 4,
        opacity: 0.85,
        line: {
          color: "rgba(31, 41, 55, 0.8)",
          width: 1
        }
      },
      text: varianceLabels,
      hoverinfo: "text+x+y+z"
    }

    const layout: Partial<Layout> = {
      paper_bgcolor: "transparent",
      plot_bgcolor: "transparent",
      font: {
        family: "JetBrains Mono, Fira Code, monospace",
        color: "#94a3b8"
      },
      scene: {
        bgcolor: "#0b0f14",
        xaxis: {
          title: varianceLabels[0] || "PC1",
          gridcolor: "#1f2937",
          linecolor: "#1f2937",
          tickcolor: "#1f2937",
          tickfont: { size: 10, color: "#94a3b8" },
          titlefont: { size: 11, color: "#94a3b8" }
        },
        yaxis: {
          title: varianceLabels[1] || "PC2",
          gridcolor: "#1f2937",
          linecolor: "#1f2937",
          tickcolor: "#1f2937",
          tickfont: { size: 10, color: "#94a3b8" },
          titlefont: { size: 11, color: "#94a3b8" }
        },
        zaxis: {
          title: varianceLabels[2] || "PC3",
          gridcolor: "#1f2937",
          linecolor: "#1f2937",
          tickcolor: "#1f2937",
          tickfont: { size: 10, color: "#94a3b8" },
          titlefont: { size: 11, color: "#94a3b8" }
        },
        camera: {
          eye: { x: 1.5, y: 1.5, z: 1.2 },
          center: { x: 0, y: 0, z: -0.1 }
        }
      },
      margin: { l: 0, r: 0, t: 8, b: 0 },
      showlegend: false,
      hoverlabel: {
        bgcolor: "#111827",
        bordercolor: "#1f2937",
        font: {
          family: "JetBrains Mono, Fira Code, monospace",
          size: 11,
          color: "#e5e7eb"
        }
      }
    }

    const config: Partial<Config> = {
      displayModeBar: false,
      responsive: true,
      scrollZoom: true
    }

    if (!plotRef.current) {
      plotRef.current = { data: [trace], layout }
      Plotly.newPlot(containerRef.current, [trace], layout, config)
    } else {
      plotRef.current.data = [trace]
      plotRef.current.layout = layout
      Plotly.react(containerRef.current, [trace], layout, config)
    }
  }, [x, y, z, color, varianceLabels, projection])

  useEffect(() => {
    let rotationTimer: ReturnType<typeof setInterval>

    const startRotation = () => {
      rotationTimer = setInterval(() => {
        if (!containerRef.current || !plotRef.current) return
        const scene = plotRef.current.layout?.scene
        if (!scene || !("camera" in scene)) return
        const cam = (scene as { camera: Camera }).camera
        if (!cam?.eye) return

        const theta = 0.008
        const cos = Math.cos(theta)
        const sin = Math.sin(theta)
        const ex = cam.eye.x * cos - cam.eye.y * sin
        const ey = cam.eye.x * sin + cam.eye.y * cos
        const ez = cam.eye.z

        const newEye = { x: ex, y: ey, z: ez }
        const newCamera = { ...cam, eye: newEye }
        Plotly.relayout(containerRef.current, {
          "scene.camera": newCamera
        })
      }, 50)
    }

    const container = containerRef.current

    const stopRotation = () => {
      clearInterval(rotationTimer)
    }

    startRotation()

    if (container) {
      container.addEventListener("mousedown", stopRotation)
      container.addEventListener("touchstart", stopRotation)
      container.addEventListener("mouseup", startRotation)
      container.addEventListener("touchend", startRotation)
    }

    return () => {
      stopRotation()
      if (container) {
        container.removeEventListener("mousedown", stopRotation)
        container.removeEventListener("touchstart", stopRotation)
        container.removeEventListener("mouseup", startRotation)
        container.removeEventListener("touchend", startRotation)
        Plotly.purge(container)
      }
    }
  }, [])

  const pointCount = projection.length
  const has3D = projection[0]?.length >= 3

  return (
    <Card title="3D PCA Explorer">
      <div className="mb-3 flex gap-3 items-center flex-wrap">
        <span className="text-xs text-muted">
          {pointCount} points · drag to rotate · scroll to zoom
        </span>
        {has3D && (
          <span
            className="text-xs px-2 py-0.5 rounded border"
            style={{
              borderColor: DRIFT_COLORS[driftClassification] || DRIFT_COLORS.unknown,
              color: DRIFT_COLORS[driftClassification] || DRIFT_COLORS.unknown
            }}
          >
            {driftClassification?.toUpperCase() || "UNKNOWN"}
          </span>
        )}
      </div>
      {!has3D && projection.length > 0 && (
        <p className="text-xs text-muted mb-2">
          Projection has {projection[0]?.length ?? 0} dimensions — 3D requires ≥3
        </p>
      )}
      <div
        ref={containerRef}
        style={{ width: "100%", height: 420 }}
      />
    </Card>
  )
}
