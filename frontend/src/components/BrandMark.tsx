import { FilesIcon } from "lucide-react"

import { cn } from "@/lib/utils"

type BrandMarkProps = {
  compact?: boolean
  className?: string
}

export function BrandMark({ compact = false, className }: BrandMarkProps) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm shadow-primary/20">
        <FilesIcon className="size-4" aria-hidden="true" />
      </span>
      {compact ? null : (
        <span className="min-w-0 leading-tight">
          <span className="block truncate text-sm font-semibold tracking-tight">
            Driftwood Capital
          </span>
          <span className="block truncate text-[11px] text-muted-foreground">
            Document Copilot
          </span>
        </span>
      )}
    </div>
  )
}
