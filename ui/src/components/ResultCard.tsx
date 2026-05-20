interface ResultCardProps {
  title: string
  items: string[]
}

export function ResultCard({ title, items }: ResultCardProps) {
  return (
    <div className="rounded-[14px] border border-border bg-card p-5">
      <h3 className="mb-3 text-[18px] font-semibold leading-[1.4] text-foreground">{title}</h3>
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <span
            key={item}
            className="rounded-[6px] bg-muted px-3 py-1 text-[13px] text-foreground"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  )
}
