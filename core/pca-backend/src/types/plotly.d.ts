declare module "plotly.js-dist-min" {
  export interface Marker {
    color?: string | number[] | string[]
    size?: number | number[]
    opacity?: number | number[]
    line?: {
      color?: string
      width?: number
    }
  }

  export interface Data {
    type: string
    mode?: string
    x?: number[]
    y?: number[]
    z?: number[]
    text?: string[] | string
    marker?: Marker
    hoverinfo?: string
  }

  export interface Font {
    family?: string
    color?: string
    size?: number
  }

  export interface Margin {
    l?: number
    r?: number
    t?: number
    b?: number
  }

  export interface Axis {
    title?: string
    gridcolor?: string
    linecolor?: string
    tickcolor?: string
    tickfont?: Partial<Font>
    titlefont?: Partial<Font>
  }

  export interface Camera {
    eye?: { x: number; y: number; z: number }
    center?: { x: number; y: number; z: number }
    up?: { x: number; y: number; z: number }
  }

  export interface Scene {
    bgcolor?: string
    xaxis?: Partial<Axis>
    yaxis?: Partial<Axis>
    zaxis?: Partial<Axis>
    camera?: Camera
  }

  export interface Hoverlabel {
    bgcolor?: string
    bordercolor?: string
    font?: Partial<Font>
  }

  export interface Layout {
    paper_bgcolor?: string
    plot_bgcolor?: string
    font?: Partial<Font>
    showlegend?: boolean
    margin?: Partial<Margin>
    scene?: Partial<Scene>
    hoverlabel?: Partial<Hoverlabel>
  }

  export interface Figure {
    data: Data[]
    layout?: Partial<Layout>
  }

  export interface Config {
    displayModeBar?: boolean
    responsive?: boolean
    scrollZoom?: boolean
    staticPlot?: boolean
  }

  export function newPlot(
    root: string | HTMLElement,
    data: Data[],
    layout?: Partial<Layout>,
    config?: Partial<Config>
  ): Promise<void>

  export function react(
    root: string | HTMLElement,
    data: Data[],
    layout?: Partial<Layout>,
    config?: Partial<Config>
  ): Promise<void>

  export function purge(root: string | HTMLElement): void

  export function relayout(
    root: string | HTMLElement,
    update: Record<string, unknown>
  ): Promise<void>

  export function resize(root: string | HTMLElement): Promise<void>

  const Plotly: {
    newPlot: typeof newPlot
    react: typeof react
    purge: typeof purge
    relayout: typeof relayout
    resize: typeof resize
  }

  export default Plotly
}
