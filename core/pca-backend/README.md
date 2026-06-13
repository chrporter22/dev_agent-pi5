# PCA Dashboard Frontend PRD

## Purpose

The PCA Dashboard is a real-time ML observability interface for OpenClaw.

The dashboard visualizes:

* PCA latent-space projections
* Explained variance
* Eigenvalues
* Drift monitoring
* Risk prediction
* ML worker health
* Historical PCA evolution

The UI is read-only and consumes data exclusively from the Node API.

---

# Architecture

```text
ML Worker
    ↓

Redis

    ↓

Node API

/api/ml/*
    ↓

React Dashboard
```

Frontend never accesses Redis directly.

---

# Design Goals

Inspired by:

* snacks.nvim dashboard
* lazy.nvim UI
* modern observability dashboards
* Grafana dark mode
* scientific visualization tools

The dashboard should feel:

* minimal
* dense
* terminal-inspired
* modern
* high signal-to-noise

---

# Color System

Primary Palette: Viridis

```text
#440154
#482777
#3E4989
#31688E
#26828E
#1F9E89
#35B779
#6CCE59
#B4DE2C
#FDE725
```

Dark Theme

Background:

```text
#0b0f14
```

Panels:

```text
#111827
```

Borders:

```text
#1f2937
```

Text:

```text
#e5e7eb
```

Muted:

```text
#94a3b8
```

---

# Layout

```text
┌────────────────────────────────────────────┐
│ OpenClaw PCA Monitoring                     │
│ heartbeat • drift • last run               │
├────────────────────────────────────────────┤
│ Drift      │ Risk      │ Variance Explained │
├────────────────────────────────────────────┤
│                                            │
│ PCA Projection Explorer                    │
│                                            │
│ X Axis: [PC1 ▼]                            │
│ Y Axis: [PC2 ▼]                            │
│                                            │
│ Scatter Plot                               │
│                                            │
├────────────────────────────────────────────┤
│ Explained Variance                         │
├────────────────────────────────────────────┤
│ Eigenvalues                                │
├────────────────────────────────────────────┤
│ PCA History Timeline                       │
└────────────────────────────────────────────┘
```

---

# PCA Explorer

User can select:

```text
PC1
PC2
PC3
PC4
...
PCN
```

for both axes.

Examples:

```text
PC1 vs PC2
PC1 vs PC3
PC2 vs PC5
PC4 vs PC7
```

Scatter updates instantly.

---

# Polling

Dashboard updates every:

```text
5 seconds
```

using:

```ts
React Query
```

---

# Required API

## Primary

```http
GET /api/ml/pca/summary
```

Used for dashboard hydration.

---

## Secondary

```http
GET /api/ml/pca/history
```

Used for timeline rendering.

---

# Dashboard Cards

## Drift

```text
Current drift score
Classification
```

Color coded:

```text
Stable
Moderate
Critical
```

---

## Risk

```text
Prediction
Confidence
```

---

## Worker Status

Displays:

```text
Heartbeat
Last Run
```

Health determined by:

heartbeat age < 30 sec

````

---

# PCA Scatter Plot

Supports:

```text
Dynamic axis selection
Zoom
Pan
Tooltip
````

Tooltip shows:

```text
Point Index
PC Value X
PC Value Y
```

---

# Variance Chart

Displays:

```text
Explained Variance Ratio
```

Per component.

Uses viridis gradient.

---

# Eigenvalue Chart

Displays:

```text
Eigenvalues
```

Per component.

Uses viridis gradient.

---

# History Timeline

Displays:

```text
Projection snapshots
```

from:

```http
/api/ml/pca/history
```

Maximum:

```text
100 records
```

---

# Technology Stack

```text
React
TypeScript
Vite
TanStack Query
Recharts
Axios
TailwindCSS
```

---

# Deployment

Container:

```text
pca-backend
```

Served through:

```text
nginx
```

All API traffic proxied to:

```text
node-api:3000
```

---

# Future Features

* websocket streaming
* PCA animation playback
* temporal drift heatmaps
* anomaly overlays
* model version display
* feature importance explorer

```
```
# pca-backend Scaffold

```text
core/
└── pca-backend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── postcss.config.js
    │
    ├── public/
    │
    └── src/
        ├── main.tsx
        ├── App.tsx
        │
        ├── api/
        │   └── mlApi.ts
        │
        ├── types/
        │   └── ml.ts
        │
        ├── hooks/
        │   ├── usePcaSummary.ts
        │   └── usePcaHistory.ts
        │
        ├── pages/
        │   └── Dashboard.tsx
        │
        ├── layouts/
        │   └── DashboardLayout.tsx
        │
        ├── components/
        │   │
        │   ├── header/
        │   │   └── DashboardHeader.tsx
        │   │
        │   ├── cards/
        │   │   ├── DriftCard.tsx
        │   │   ├── RiskCard.tsx
        │   │   ├── WorkerCard.tsx
        │   │   └── VarianceSummaryCard.tsx
        │   │
        │   ├── charts/
        │   │   ├── PCAExplorer.tsx
        │   │   ├── VarianceChart.tsx
        │   │   ├── EigenvalueChart.tsx
        │   │   └── HistoryTimeline.tsx
        │   │
        │   └── ui/
        │       ├── Card.tsx
        │       ├── Badge.tsx
        │       ├── Select.tsx
        │       └── SectionTitle.tsx
        │
        └── styles/
            ├── globals.css
            ├── viridis.css
            └── dashboard.css
```

---
Optional (recommended next step)

1. index.html injection setup
meta tags for dark mode
preload fonts (JetBrains Mono)
OpenGraph preview for dashboards

2. Loading splash screen
“Booting PCA runtime…”
live simulated heartbeat until /pca/summary loads

3. Real-time upgrade
replace polling with WebSocket:
ml:heartbeat stream
pca:update stream
drift:update stream
