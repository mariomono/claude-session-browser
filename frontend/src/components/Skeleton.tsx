const ROWS = 8;
/** Varying widths so the placeholder reads as text rather than a grid of bars. */
const WIDTHS = ["72%", "54%", "88%", "63%", "80%", "47%", "69%", "58%"];

/** Shimmering placeholder rows shown until the first session list arrives. */
export function SkeletonRows({ columns }: { columns: number }) {
  return (
    <>
      {Array.from({ length: ROWS }, (_, r) => (
        <tr key={r} className="skeleton-row" aria-hidden="true">
          {Array.from({ length: columns }, (_, c) => (
            <td key={c}>
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
