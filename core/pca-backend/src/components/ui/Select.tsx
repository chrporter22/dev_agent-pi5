interface Props {
  value: number
  options: string[]
  onChange: (value: number) => void
}

export default function Select({
  value,
  options,
  onChange
}: Props) {
  return (
    <select
      value={value}
      onChange={e =>
        onChange(Number(e.target.value))
      }
      className="
      bg-background
      border
      border-border
      rounded-lg
      px-3
      py-2
      text-sm
      "
    >
      {options.map((option, index) => (
        <option
          key={option}
          value={index}
        >
          {option}
        </option>
      ))}
    </select>
  )
}
