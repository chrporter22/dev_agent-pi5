import {
  ReactNode
}
from "react"

interface Props {
  children: ReactNode
}

export default function DashboardLayout({
  children
}: Props) {

  return (

    <main
      className="
      min-h-screen
      bg-background
      text-text
      font-mono
      "
    >

      <div
        className="
        mx-auto
        max-w-[1800px]
        p-6
        "
      >
        {children}
      </div>

    </main>
  )
}
