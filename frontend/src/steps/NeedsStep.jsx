import { useState } from "react";

const SEGMENTS = [
  ["micro", "Shop / micro retail & services"],
  ["prof", "Professional office (clinic, CA, agency)"],
  ["multi", "Multi-site business"],
  ["mfg", "Small manufacturer"],
];

export default function NeedsStep({ products, lead, gstinActive, initial, onBack, onDone }) {
  const start = initial || lead?.profile || {};
  const [segment, setSegment] = useState(start.segment || "micro");
  const [tier, setTier] = useState(start.city_tier || 1);
  const [employees, setEmployees] = useState(start.employees || 5);
  const [sites, setSites] = useState(start.sites || 1);
  const [fibre, setFibre] = useState(start.fibre_feasible ?? true);
  const [interests, setInterests] = useState(new Set(start.interests || []));

  const toggle = (id) => setInterests((s) => {
    const n = new Set(s);
    n.has(id) ? n.delete(id) : n.add(id);
    return n;
  });

  const submit = () => onDone({
    segment, city_tier: +tier, employees: Math.max(1, +employees), sites: Math.max(1, +sites),
    fibre_feasible: fibre, gstin_active: gstinActive, interests: [...interests],
  });

  return (
    <div className="step">
      <h2>What do you need?</h2>
      <div className="grid2">
        <label>Business type
          <select value={segment} onChange={(e) => setSegment(e.target.value)}>
            {SEGMENTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label>City
          <select value={tier} onChange={(e) => setTier(+e.target.value)}>
            <option value={1}>Tier-1 city</option><option value={2}>Tier-2 city</option>
          </select>
        </label>
        <label>Employees<input type="number" min={1} value={employees} onChange={(e) => setEmployees(e.target.value)} /></label>
        <label>Sites / branches<input type="number" min={1} value={sites} onChange={(e) => setSites(e.target.value)} /></label>
        <label>Fibre available at your address?
          <select value={fibre ? "1" : "0"} onChange={(e) => setFibre(e.target.value === "1")}>
            <option value="1">Yes / not sure</option><option value="0">No - checked, not available</option>
          </select>
        </label>
      </div>
      <p>Interested in <span className="muted">(optional)</span></p>
      <div className="chips">
        {products.map((p) => (
          <button key={p.product_id} className={`chip ${interests.has(p.product_id) ? "on" : ""}`}
            onClick={() => toggle(p.product_id)}>{p.product_name}</button>
        ))}
      </div>
      <div className="actions">
        <button className="secondary" onClick={onBack}>Back</button>
        <button onClick={submit}>Show my options</button>
      </div>
    </div>
  );
}
