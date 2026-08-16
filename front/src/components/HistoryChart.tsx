import type { HistoryPoint, MethodologyBreak } from "../api/types";
import { HISTORY } from "../content/copy";
import styles from "./HistoryChart.module.css";

/**
 * A multi-year series, drawn as inline SVG. No charting library.
 *
 * The library question was decided against on neutrality grounds rather than
 * weight: every general-purpose charting library ships trend lines, smoothing,
 * regression overlays and value-based colour scales as one prop away, and the
 * charter (§10) forbids all of them. Hand-rolled SVG has no such prop to
 * accidentally pass, which is the same reasoning that keeps `variant` off
 * `Figure`.
 *
 * The central design problem of this component is subtler than the forbidden
 * list, though. The 2021 baccalauréat reform changed the examination, but the
 * stored total-level series is *perfectly continuous* across it — verified on
 * the loaded data. So a naive line runs straight through a methodology change
 * with nothing to hint at it, and a reader's eye will read the two sides as
 * comparable. Hence:
 *
 *   - the polyline is BROKEN at a rupture year, not merely annotated. The
 *     visual discontinuity is the warning; the label explains it.
 *   - it is also broken across any year the source did not publish. A missing
 *     year is left empty (§10), never interpolated — joining across a gap
 *     would draw a value nobody measured.
 *
 * There is no `trend`, `projection`, `smooth` or `forecast` prop, and no code
 * path that fits a line to the points.
 */
export interface HistoryChartProps {
  points: HistoryPoint[];
  breaks: MethodologyBreak[];
  /** Accessible title. Descriptive only — never a conclusion about the data. */
  title: string;
  unit: string;
}

const WIDTH = 720;
const HEIGHT = 260;
const PAD = { top: 24, right: 16, bottom: 40, left: 48 };

interface Plotted {
  year: number;
  value: number;
  x: number;
  y: number;
}

/**
 * Split the series wherever the line must not be drawn.
 *
 * A segment ends when the next year is not exactly one later (a gap the source
 * did not publish) or when a rupture falls between the two points.
 */
function toSegments(plotted: Plotted[], breakYears: Set<number>): Plotted[][] {
  const segments: Plotted[][] = [];
  let current: Plotted[] = [];

  for (const [index, point] of plotted.entries()) {
    if (index === 0) {
      current = [point];
      continue;
    }
    const previous = plotted[index - 1];
    const isConsecutive = point.year === previous.year + 1;
    const crossesBreak = breakYears.has(point.year);

    if (isConsecutive && !crossesBreak) {
      current.push(point);
    } else {
      segments.push(current);
      current = [point];
    }
  }
  if (current.length > 0) segments.push(current);
  return segments;
}

export function HistoryChart({ points, breaks, title, unit }: HistoryChartProps) {
  const withValues = points.filter((point) => point.valeur !== null);

  if (withValues.length === 0) {
    return <p className={styles.empty}>{HISTORY.noSeriesData}</p>;
  }

  const years = withValues.map((p) => p.annee);
  const values = withValues.map((p) => p.valeur as number);
  const minYear = Math.min(...years);
  const maxYear = Math.max(...years);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  // Pad the value axis so a flat series is not drawn as a line pinned to an
  // edge, which would read as an extreme.
  const low = Math.min(minValue, 0) === 0 && minValue >= 0 ? 0 : minValue - 2;
  const high = maxValue + 2;
  const span = high - low || 1;
  const yearSpan = maxYear - minYear || 1;

  const plotX = (year: number) =>
    PAD.left + ((year - minYear) / yearSpan) * (WIDTH - PAD.left - PAD.right);
  const plotY = (value: number) =>
    HEIGHT - PAD.bottom - ((value - low) / span) * (HEIGHT - PAD.top - PAD.bottom);

  const plotted: Plotted[] = withValues.map((point) => ({
    year: point.annee,
    value: point.valeur as number,
    x: plotX(point.annee),
    y: plotY(point.valeur as number),
  }));

  const breakYears = new Set(breaks.map((item) => item.annee));
  const segments = toSegments(plotted, breakYears);

  return (
    <figure className={styles.figure}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className={styles.svg}
        role="img"
        aria-label={title}
      >
        {/* Baseline only. No gridlines keyed to a "target" value: there is no
            target, and drawing one would invent a threshold to be judged by. */}
        <line
          x1={PAD.left}
          y1={HEIGHT - PAD.bottom}
          x2={WIDTH - PAD.right}
          y2={HEIGHT - PAD.bottom}
          className={styles.axis}
        />

        {breaks.map((item) => (
          <g key={item.annee}>
            <line
              x1={plotX(item.annee) - 6}
              y1={PAD.top}
              x2={plotX(item.annee) - 6}
              y2={HEIGHT - PAD.bottom}
              className={styles.breakLine}
            />
            <text
              x={plotX(item.annee) - 10}
              y={PAD.top - 8}
              className={styles.breakLabel}
              textAnchor="end"
            >
              {item.annee}
            </text>
          </g>
        ))}

        {segments.map((segment, index) => (
          <polyline
            key={`segment-${index}`}
            className={styles.line}
            fill="none"
            points={segment.map((p) => `${p.x},${p.y}`).join(" ")}
          />
        ))}

        {plotted.map((point) => (
          <circle
            key={point.year}
            cx={point.x}
            cy={point.y}
            r={3.5}
            className={styles.point}
          />
        ))}

        <text x={PAD.left} y={HEIGHT - 12} className={styles.axisLabel}>
          {minYear}
        </text>
        <text
          x={WIDTH - PAD.right}
          y={HEIGHT - 12}
          className={styles.axisLabel}
          textAnchor="end"
        >
          {maxYear}
        </text>
      </svg>

      <figcaption className={styles.caption}>
        {title} · {unit}
      </figcaption>
    </figure>
  );
}
