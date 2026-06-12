websocket streaming
PCA animation playback
temporal drift heatmaps
anomaly overlays
model version display
feature importance explorer


Recommended Updated Scaffold
src/
├── api/
│   └── mlApi.ts
│
├── components/
│
│   ├── cards/
│   │   ├── DriftCard.tsx
│   │   ├── RiskCard.tsx
│   │   ├── HeartbeatCard.tsx
│   │   └── VarianceCard.tsx
│   │
│   ├── charts/
│   │   ├── PCAExplorer.tsx
│   │   ├── VarianceChart.tsx
│   │   ├── EigenvalueChart.tsx
│   │   └── HistoryTimeline.tsx
│   │
│   ├── layout/
│   │   ├── DashboardHeader.tsx
│   │   ├── DashboardGrid.tsx
│   │   └── DashboardShell.tsx
│   │
│   └── ui/
│       ├── Card.tsx
│       ├── Select.tsx
│       └── Badge.tsx
│
├── hooks/
│   ├── usePcaSummary.ts
│   └── useHistory.ts
│
├── styles/
│   ├── globals.css
│   └── viridis.css
│
├── pages/
│   └── Dashboard.tsx
│
├── types/
│   └── ml.ts
│
├── App.tsx
└── main.tsx
PCA Explorer Component

The major upgrade:

const [xAxis, setXAxis] = useState(0)
const [yAxis, setYAxis] = useState(1)

Controls:

<select value={xAxis}>
  PC1
  PC2
  PC3
  PC4
</select>

<select value={yAxis}>
  PC1
  PC2
  PC3
  PC4
</select>

Projection mapping:

const data = projection.map(
  (row, index) => ({
    id: index,
    x: row[xAxis],
    y: row[yAxis]
  })
)

Rendering:

<ScatterChart>
  <Scatter
    data={data}
    fill="var(--viridis-7)"
  />
</ScatterChart>
Viridis Theme Tokens
:root {

  --bg: #0b0f14;
  --panel: #111827;
  --border: #1f2937;

  --viridis-1: #440154;
  --viridis-2: #482777;
  --viridis-3: #3e4989;
  --viridis-4: #31688e;
  --viridis-5: #26828e;
  --viridis-6: #1f9e89;
  --viridis-7: #35b779;
  --viridis-8: #6cce59;
  --viridis-9: #b4de2c;
  --viridis-10: #fde725;
}
Snacks.nvim Style Header
 ██████╗ ██████╗ █████╗
 ██╔══██╗██╔════╝██╔══██╗
 ██████╔╝██║     ███████║
 ██╔═══╝ ██║     ██╔══██║
 ██║     ╚██████╗██║  ██║

 PCA MONITORING DASHBOARD

Header row:

● ML ONLINE
● Drift: Stable
● Risk: Low
● Updated: 2s ago
Dashboard Grid
grid-template-columns:
repeat(12, 1fr);

Cards:

┌─────┬─────┬─────┐
│Drift│Risk │Alive│
└─────┴─────┴─────┘

┌─────────────────┐
│ PCA Explorer    │
└─────────────────┘

┌────────┬────────┐
│Variance│Eigen   │
└────────┴────────┘

┌─────────────────┐
│ History         │
└─────────────────┘
