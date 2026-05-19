interface SkeletonBlockProps {
  lines?: number
}

export function SkeletonBlock({ lines = 3 }: SkeletonBlockProps) {
  return (
    <div className="space-y-3">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-4 animate-pulse rounded bg-[#E8E4DD] dark:bg-[#3D3A35]"
          style={{ width: i === lines - 1 ? '60%' : '100%' }}
        />
      ))}
    </div>
  )
}
