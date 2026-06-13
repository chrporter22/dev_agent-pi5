import { ReactNode } from "react"

interface Props {
  title?: string
  children: ReactNode
  className?: string
}

export default function Card({
  title,
  children,
  className = ""
}: Props) {
  return (
    <div
      className={`
        bg-panel
        border
        border-border
        rounded-xl
        p-5
        shadow-panel
        ${className}
      `}
    >
      {title && (
        <h3
          className="
          text-sm
          uppercase
          tracking-wider
          text-muted
          mb-4
          "
        >
          {title}
        </h3>
      )}

      {children}
    </div>
  )
}
