import { useState } from "react";
import { api } from "../api.js";
import { Result } from "../components/ui.jsx";

export default function BusinessStep({ demoLeads, value, onDone }) {
  const [gstinInput, setGstinInput] = useState(value.gstin || "");
  const [udyamInput, setUdyamInput] = useState(value.udyam || "");
  const [gst, setGst] = useState(null);          // lookup response
  const [udyam, setUdyam] = useState(null);
  const [lead, setLead] = useState(value.lead);
  const [noGstin, setNoGstin] = useState(false);

  async function verifyGstin(g = gstinInput) {
    const r = await api("gstin/" + encodeURIComponent(g.trim()));
    setGst({ ...r, gstin: g.trim().toUpperCase() });
    return r;
  }

  async function verifyUdyam(u = udyamInput, g = gst?.gstin) {
    setUdyam(await api(`udyam/${encodeURIComponent(u.trim())}?gstin=${encodeURIComponent(g || "")}`));
  }

  async function loadLead(id) {
    if (!id) return;
    const l = await api("leads/" + id);
    setLead(l);
    setGstinInput(l.gstin);
    setUdyamInput(l.udyam_number);
    await verifyGstin(l.gstin);
    if (l.udyam_number) await verifyUdyam(l.udyam_number, l.gstin);
    else setUdyam(null);
  }

  const verified = gst?.ok ? gst.gstin : null;

  return (
    <div className="step">
      <h2>Tell us about your business</h2>
      <p className="muted">Enter your GSTIN and we fill in the rest from the GST registry. No visit needed.</p>
      <div className="demo">
        Demo:{" "}
        <select defaultValue="" onChange={(e) => loadLead(e.target.value)}>
          <option value="">load a sample lead…</option>
          {demoLeads.map((l) => (
            <option key={l.lead_id} value={l.lead_id}>{l.applicant} · {l.business_name}, {l.city}</option>
          ))}
        </select>
      </div>

      <div className="row">
        <label>GSTIN
          <input value={gstinInput} maxLength={15} placeholder="e.g. 27QTBXZ1995X1Z9" autoComplete="off"
            onChange={(e) => setGstinInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && verifyGstin()} />
        </label>
        <button onClick={() => verifyGstin()}>Verify</button>
      </div>
      {gst && (gst.ok
        ? <Result kind="ok" title={`${gst.record.trade_name} · ${gst.record.constitution} · GST ${gst.record.status}`}>
            <div className="muted">{gst.record.legal_name} — {gst.record.principal_place_of_business}</div>
          </Result>
        : <Result kind="bad" lines={gst.errors} />)}

      <div className="row">
        <label>Udyam number <span className="muted">(optional)</span>
          <input value={udyamInput} placeholder="UDYAM-MH-00-1234567" autoComplete="off"
            onChange={(e) => setUdyamInput(e.target.value)} />
        </label>
        <button className="secondary" onClick={() => verifyUdyam()}>Verify</button>
      </div>
      {udyam && (udyam.ok
        ? <Result kind="ok" title={udyam.record.enterprise_name}>
            <div>{udyam.record.enterprise_type} enterprise · {udyam.record.nic_description}</div>
          </Result>
        : <Result kind="bad" lines={udyam.errors} />)}

      <label className="check">
        <input type="checkbox" checked={noGstin} onChange={(e) => setNoGstin(e.target.checked)} /> I don't have a GSTIN yet
      </label>
      <div className="actions">
        <button disabled={!verified && !noGstin}
          onClick={() => onDone({ gstin: verified, udyam: udyam?.ok ? udyamInput.trim().toUpperCase() : "", lead })}>
          Continue
        </button>
      </div>
    </div>
  );
}
