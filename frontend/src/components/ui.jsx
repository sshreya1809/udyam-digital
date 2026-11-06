export function Verdict({ value }) {
  const label = { MISSING: "Not uploaded", READING: "Reading…" }[value] || value;
  return <span className={`v ${value === "READING" ? "MISSING" : value}`}>{label}</span>;
}

export function Result({ kind, title, lines = [], children }) {
  return (
    <div className={`result ${kind}`}>
      {title && <b>{title}</b>}
      {lines.map((l, i) => <div key={i}>{l}</div>)}
      {children}
    </div>
  );
}

export function Findings({ findings }) {
  if (!findings.length) return <ul className="findings"><li>Looks good ✓</li></ul>;
  return (
    <ul className="findings">
      {findings.map((f, i) => (
        <li key={i} className={f.severity}>{f.severity === "WARN" ? "⚠ " : ""}{f.message}</li>
      ))}
    </ul>
  );
}

export function Fields({ fields }) {
  return (
    <div className="fields">
      {Object.entries(fields).map(([k, v]) => `${k}: ${v}`).join(" · ")}
    </div>
  );
}
