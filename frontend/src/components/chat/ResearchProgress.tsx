import { FileTextIcon, SearchIcon, ShieldCheckIcon } from "lucide-react"

import { Spinner } from "@/components/ui/spinner"
import { cn } from "@/lib/utils"

type ResearchProgressProps = {
  status: "submitted" | "streaming"
}

export function ResearchProgress({ status }: ResearchProgressProps) {
  const isSearching = status === "submitted"
  const label = isSearching
    ? "Searching filing passages…"
    : "Preparing and validating the cited answer…"

  return (
    <div className="mr-auto flex max-w-xl items-center gap-3" role="status">
      <div className="relative flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-primary/20 bg-primary/5 text-primary">
        <FileTextIcon className="size-5" aria-hidden="true" />
        <span
          className="research-scan absolute inset-x-2 h-px bg-primary shadow-[0_0_8px_var(--primary)]"
          aria-hidden="true"
        />
      </div>
      <div>
        <div className="flex items-center gap-2 text-sm font-medium">
          <Spinner className="size-3.5 text-primary motion-reduce:hidden" />
          {label}
        </div>
        <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
          <span
            className={cn("flex items-center gap-1", isSearching && "text-primary")}
          >
            <SearchIcon className="size-3" aria-hidden="true" />
            Retrieve
          </span>
          <span
            className={cn("flex items-center gap-1", !isSearching && "text-primary")}
          >
            <ShieldCheckIcon className="size-3" aria-hidden="true" />
            Ground
          </span>
        </div>
      </div>
    </div>
  )
}
