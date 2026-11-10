import type { KeyboardEvent } from "react"

import type { AnswerChart as AnswerChartData, CitationSource } from "@/lib/chat-messages"

type AnswerChartProps = {
  chart: AnswerChartData
  citations: CitationSource[]
  onCitationSelect: (citation: CitationSource) => void
}

const WIDTH = 760
const HEIGHT = 340
const MARGIN = { top: 20, right: 18, bottom: 48, left: 68 }
const COLORS = [
  "var(--primary)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--foreground)",
]

const compactNumber = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
})
const fullNumber = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 2,
})

export function AnswerChart({
  chart,
  citations,
  onCitationSelect,
}: AnswerChartProps) {
  const labels = chart.series[0].points.map((point) => point.label)
  const values = chart.series.flatMap((series) =>
    series.points.map((point) => point.value),
  )
  const minimum = Math.min(0, ...values)
  const maximum = Math.max(0, ...values)
  const range = maximum - minimum || 1
  const plotWidth = WIDTH - MARGIN.left - MARGIN.right
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom
  const groupWidth = plotWidth / labels.length
  const barWidth = Math.max(
    4,
    Math.min(30, (groupWidth - 14) / chart.series.length),
  )
  const seriesWidth = barWidth * chart.series.length
  const y = (value: number) =>
    MARGIN.top + ((maximum - value) / range) * plotHeight
  const zeroY = y(0)
  const citationsByPosition = new Map(
    citations.map((citation) => [citation.position, citation]),
  )
  const ticks = Array.from({ length: 5 }, (_, index) => {
    const value = maximum - (range * index) / 4
    return { value, y: y(value) }
  })

  function openCitation(position: number) {
    const citation = citationsByPosition.get(position)
    if (citation) {
      onCitationSelect(citation)
    }
  }

  function handleBarKeyDown(
    event: KeyboardEvent<SVGGElement>,
    citationPosition: number,
  ) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      openCitation(citationPosition)
    }
  }

  return (
    <figure className="mt-5 overflow-hidden rounded-xl border bg-card shadow-xs">
      <figcaption className="border-b px-4 py-3">
        <p className="text-sm font-semibold text-foreground">{chart.title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{chart.unit}</p>
      </figcaption>
      <div className="overflow-x-auto px-2 py-3 sm:px-4">
        <svg
          className="min-w-[640px]"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={`${chart.title}, measured in ${chart.unit}`}
        >
          {ticks.map((tick) => (
            <g key={tick.value}>
              <line
                x1={MARGIN.left}
                x2={WIDTH - MARGIN.right}
                y1={tick.y}
                y2={tick.y}
                stroke="var(--border)"
                strokeDasharray="3 4"
              />
              <text
                x={MARGIN.left - 10}
                y={tick.y + 4}
                fill="var(--muted-foreground)"
                fontSize="11"
                textAnchor="end"
              >
                {compactNumber.format(tick.value)}
              </text>
            </g>
          ))}
          <line
            x1={MARGIN.left}
            x2={WIDTH - MARGIN.right}
            y1={zeroY}
            y2={zeroY}
            stroke="var(--foreground)"
            strokeOpacity="0.45"
          />
          {labels.map((label, labelIndex) => (
            <text
              key={label}
              x={MARGIN.left + groupWidth * (labelIndex + 0.5)}
              y={HEIGHT - 20}
              fill="var(--muted-foreground)"
              fontSize="12"
              textAnchor="middle"
            >
              {label}
            </text>
          ))}
          {chart.series.flatMap((series, seriesIndex) =>
            series.points.map((point, pointIndex) => {
              const pointY = y(point.value)
              const x =
                MARGIN.left +
                groupWidth * (pointIndex + 0.5) -
                seriesWidth / 2 +
                seriesIndex * barWidth
              const barY = point.value >= 0 ? pointY : zeroY
              const height = Math.max(1, Math.abs(zeroY - pointY))
              return (
                <g
                  key={`${series.label}-${point.label}`}
                  className="cursor-pointer outline-none focus-visible:opacity-70"
                  role="button"
                  tabIndex={0}
                  aria-label={`${series.label}, ${point.label}: ${fullNumber.format(point.value)} ${chart.unit}. Open citation ${point.citation_position}.`}
                  onClick={() => openCitation(point.citation_position)}
                  onKeyDown={(event) =>
                    handleBarKeyDown(event, point.citation_position)
                  }
                >
                  <title>
                    {series.label} · {point.label}: {fullNumber.format(point.value)} {chart.unit}
                  </title>
                  <rect
                    x={x + 1}
                    y={barY}
                    width={Math.max(2, barWidth - 2)}
                    height={height}
                    rx="2"
                    fill={COLORS[seriesIndex]}
                    className="transition-opacity hover:opacity-75"
                  />
                </g>
              )
            }),
          )}
        </svg>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-2 border-t px-4 py-3">
        {chart.series.map((series, index) => (
          <span
            key={series.label}
            className="flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            <span
              className="size-2.5 rounded-sm"
              style={{ backgroundColor: COLORS[index] }}
              aria-hidden="true"
            />
            {series.label}
          </span>
        ))}
        <span className="ml-auto text-[11px] text-muted-foreground">
          Select a bar to inspect its source
        </span>
      </div>
    </figure>
  )
}
