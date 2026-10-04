import { ExternalLinkIcon, FileCheck2Icon, QuoteIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import type { CitationSource } from "@/lib/chat-messages"

type SourcePassagePanelProps = {
  citation: CitationSource | null
  onClose: () => void
}

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "numeric",
})

function sourceLocation(citation: CitationSource) {
  const values = []
  if (citation.page !== null) {
    values.push(`Page ${citation.page}`)
  }
  if (citation.section) {
    values.push(citation.section)
  }
  return values.join(" · ") || "Location unavailable"
}

export function SourcePassagePanel({
  citation,
  onClose,
}: SourcePassagePanelProps) {
  return (
    <Sheet open={citation !== null} onOpenChange={(open) => !open && onClose()}>
      {citation ? (
        <SheetContent className="w-full overflow-y-auto p-0 sm:max-w-xl">
          <SheetHeader className="border-b bg-muted/30 px-6 py-5">
            <div className="mb-2 flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <FileCheck2Icon className="size-4" aria-hidden="true" />
            </div>
            <SheetTitle className="pr-8 text-xl tracking-tight">
              {citation.company_name ?? citation.ticker}
            </SheetTitle>
            <SheetDescription>
              {citation.ticker} · {citation.form} ·{" "}
              {dateFormatter.format(new Date(`${citation.filing_date}T00:00:00`))}
            </SheetDescription>
          </SheetHeader>

          <div className="flex flex-1 flex-col gap-6 px-6 py-6">
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">Citation {citation.position}</Badge>
              <Badge variant="outline">{sourceLocation(citation)}</Badge>
            </div>

            <div>
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                <QuoteIcon className="size-3" aria-hidden="true" />
                Exact cited passage
              </p>
              <blockquote className="mt-3 rounded-xl border border-primary/15 bg-primary/5 p-5 text-sm leading-7 text-foreground">
                {citation.quoted_text}
              </blockquote>
            </div>

            <div className="mt-auto border-t pt-4">
              <p className="mb-3 text-xs text-muted-foreground">
                SEC accession {citation.accession_number}
              </p>
              <Button asChild className="w-full sm:w-auto" variant="outline">
                <a
                  href={citation.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open filing
                  <ExternalLinkIcon data-icon="inline-end" />
                </a>
              </Button>
            </div>
          </div>
        </SheetContent>
      ) : null}
    </Sheet>
  )
}
