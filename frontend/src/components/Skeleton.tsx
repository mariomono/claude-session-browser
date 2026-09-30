const ROWS = 8;
/** Varying widths so the placeholder reads as text rather than a grid of bars. */
const WIDTHS = ["72%", "54%", "88%", "63%", "80%", "47%", "69%", "58%"];

/** Shimmering placeholder rows shown until the first session list arrives; one cell per column class. */
export function SkeletonRows({ columns }: { columns: readonly string[] }) {
  return (
    <>
      {Array.from({ length: ROWS }, (_, r) => (
        <tr key={r} className="skeleton-row" aria-hidden="true">
          {columns.map((cls, c) => (
            <td key={c} className={cls}>
              <span className="skeleton" style={{ width: c === 0 ? "16px" : WIDTHS[(r + c) % WIDTHS.length] }} />
              {(c === 1 || c === 3) && (
                <span className="skeleton skeleton--sub" style={{ width: WIDTHS[(r + c + 3) % WIDTHS.length] }} />
              )}
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}
