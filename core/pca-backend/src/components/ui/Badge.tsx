interface Props {
  label: string
  color?: string
}

export default function Badge({
  label,
  color = "bg-viridis-600"
}: Props) {
  return (
    <span
      className={`
        px-2
        py-1
        rounded-md
        text-xs
        font-semibold
        text-black
        ${color}
      `}
    >
      {label}
    </span>
  )
}
