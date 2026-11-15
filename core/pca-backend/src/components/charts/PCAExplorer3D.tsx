import { useEffect, useRef, useMemo, useState } from "react"

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

function zscore(arr: number[]) {
  if (arr.length < 2) return arr.map(() => 0)
  const mean = arr.reduce((a, b) => a + b, 0) / arr.length
  const std = Math.sqrt(arr.reduce((s, v) => s + (v - mean) ** 2, 0) / arr.length)
  if (std === 0) return arr.map(() => 0)
  return arr.map((v) => (v - mean) / std)
}

function viridisColor(t: number) {
  const colors = [
    "#440154", "#482777", "#3e4989", "#31688e", "#26828e",
    "#1f9e89", "#35b779", "#6cce59", "#b4de2c", "#fde725"
  ]
  const idx = Math.min(Math.max(Math.floor(t * colors.length), 0), colors.length - 1)
  return colors[idx]
}

export default function PCAExplorer3D({
  projection,
  variance = [],
  driftClassification = "unknown"
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const plotRef = useRef<Figure | null>(null)
  const [dimIndex, setDimIndex] = useState(0)

  const dims = useMemo(() => {
    const n = projection[0]?.length ?? 0
    const combos: [number, number, number][] = []
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        for (let k = j + 1; k < n; k++) {
          combos.push([i, j, k])
        }
      }
    }
    if (combos.length === 0) return [[0, 1, 2]]
    return combos.length > 3 ? combos.slice(0, 4) : combos
  }, [projection])

  const { x, y, z, colors, sizes, zValues } = useMemo(() => {
    const [i, j, k] = dims[dimIndex] || [0, 1, 2]
    const xRaw = projection.map((row) => row[i] ?? 0)
    const yRaw = projection.map((row) => row[j] ?? 0)
    const zRaw = projection.map((row) => row[k] ?? 0)

    const zScores = zscore(zRaw)
    const colors = zScores.map((z) => viridisColor((z + 3) / 6))
    const sizes = zScores.map((z) => 3 + Math.abs(z) * 3)

    return { x: xRaw, y: yRaw, z: zRaw, colors, sizes, zValues: zScores }
  }, [projection, dimIndex, dims])

  const varianceLabels = useMemo(() => {
    const total = variance.reduce((s, v) => s + v, 0) || 1
    return variance.map((v, i) => `PC${i + 1} · ${((v / total) * 100).toFixed(1)}%`)
  }, [variance])

  const currentDims = dims[dimIndex] || [0, 1, 2]
  const dimLabels = [
    varianceLabels[currentDims[0]] || `PC${currentDims[0] + 1}`,
    varianceLabels[currentDims[1]] || `PC${currentDims[1] + 1}`,
    varianceLabels[currentDims[2]] || `PC${currentDims[2] + 1}`
  ]

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
        color: colors,
        size: sizes,
        opacity: 0.9,
        line: {
          color: colors.map((c) => {
            const r = parseInt(c.slice(1, 3), 16)
            const g = parseInt(c.slice(3, 5), 16)
            const b = parseInt(c.slice(5, 7), 16)
            return `rgba(${Math.min(r + 60, 255)}, ${Math.min(g + 60, 255)}, ${Math.min(b + 60, 255)}, 0.6)`
          }),
          width: 2
        }
      },
      text: zValues.map((z) => `z: ${z.toFixed(2)}`),
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
          title: dimLabels[0],
          gridcolor: "#1f2937",
          linecolor: "#1f2937",
          tickcolor: "#1f2937",
          tickfont: { size: 10, color: "#94a3b8" },
          titlefont: { size: 11, color: "#94a3b8" }
        },
        yaxis: {
          title: dimLabels[1],
          gridcolor: "#1f2937",
          linecolor: "#1f2937",
          tickcolor: "#1f2937",
          tickfont: { size: 10, color: "#94a3b8" },
          titlefont: { size: 11, color: "#94a3b8" }
        },
        zaxis: {
          title: dimLabels[2],
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
  }, [x, y, z, colors, sizes, dimLabels, projection])

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
  const dimCount = dims.length

  return (
    <Card title="3D PCA Explorer">
      <div className="mb-3 flex gap-2 items-center flex-wrap justify-between">
        <div className="flex gap-2 items-center">
          <span className="text-xs text-muted">
            {pointCount} pts · z: {zValues.length > 0 ? `${zValues[0].toFixed(2)}` : "—"}…{zValues.length > 0 ? zValues[zValues.length - 1].toFixed(2) : ""}
          </span>
          {has3D && (
            <span
              className="text-xs px-2 py-0.5 rounded border"
              style={{
                borderColor: "#35b779",
                color: "#35b779"
              }}
            >
              {driftClassification?.toUpperCase() || "UNKNOWN"}
            </span>
          )}
        </div>
        {dimCount > 1 && (
          <div className="flex gap-1">
            {dims.map((d, i) => (
              <button
                key={i}
                onClick={() => setDimIndex(i)}
                className={`
                  text-xs px-2 py-1 rounded border transition-all
                  ${i === dimIndex
                    ? "border-[#35b779] bg-[#35b779]/20 text-[#35b779]"
                    : "border-border text-muted hover:border-[#35b779]/50 hover:text-[#35b779]"
                  }
                `}
              >
                {`PC${d[0] + 1}-PC${d[1] + 1}-PC${d[2] + 1}`}
              </button>
            ))}
          </div>
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
