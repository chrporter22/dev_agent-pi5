interface Props {
  title: string
}

export default function SectionTitle({
  title
}: Props) {
  return (
    <h2
      className="
      text-lg
      font-semibold
      mb-4
      text-viridis-700
      "
    >
      {title}
    </h2>
  )
}
