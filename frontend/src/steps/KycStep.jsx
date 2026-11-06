import { useState } from "react";
import { api, SLOTS, toBase64 } from "../api.js";
import { Fields, Findings, Result, Verdict } from "../components/ui.jsx";

function ConsentNotice({ onAccept }) {
  const [agreed, setAgreed] = useState(false);
  return (
    <div className="notice">
      <h3>Before you upload</h3>
      <ul>
        <li>We use your documents <b>only</b> to verify your business and authorised signatory for this connection.</li>
        <li>We read them automatically and show you any problem straight away, so you can fix it in minutes.</li>
        <li>Document images are never stored; only the extracted fields and the result are kept, with identifiers masked.</li>
        <li>Extracted data is deleted 30 days after your request closes, unless the law requires longer.</li>
      </ul>
      <label className="check">
        <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} /> I agree to this use of my documents
      </label>
      <button disabled={!agreed} onClick={onAccept}>Continue</button>
    </div>
  );
}

export default function KycStep({ app, setApp, demoLeads, onVerified }) {
  const [results, setResults] = useState({});
  const [reading, setReading] = useState({});
  const [error, setError] = useState("");

  async function consent() {
    setApp(await api(`applications/${app.id}/consent`, { accepted: true }));
  }

  async function upload(slot, blob) {
    setError("");
    setReading((r) => ({ ...r, [slot]: true }));
    try {
      const r = await api(`applications/${app.id}/documents`, { slot, image_base64: await toBase64(blob) });
      setResults((x) => ({ ...x, [slot]: r }));
      setApp(r.application);
    } catch (e) {
      setError(e.message);
    } finally {
      setReading((r) => ({ ...r, [slot]: false }));
    }
  }

  async function loadSamplePack(k) {
    if (!k) return;
    for (const slot of Object.keys(SLOTS)) {
      const r = await fetch(`/samples/${k}_${slot}.png`);
      if (r.ok) await upload(slot, await r.blob());
    }
  }

  async function submit() {
    setError("");
    try {
      const a = await api(`applications/${app.id}/submit`, {});
      setApp(a);
      if (a.kyc.verdict === "PASS") setTimeout(onVerified, 900);
    } catch (e) {
      setError(e.message);
    }
  }

  if (!app.consent) return <div className="step"><h2>Upload documents</h2><ConsentNotice onAccept={consent} /></div>;

  const slots = Object.keys(SLOTS).filter((s) => app.required_documents.includes(s) || results[s]);
  const k = app.kyc;
  const issues = k ? Object.values(k.documents).flatMap((d) =>
    d.findings.filter((f) => f.severity !== "WARN").map((f) => `${d.label}: ${f.message}`)) : [];

  return (
    <div className="step">
      <h2>Upload documents</h2>
      <div className="demo">
        Demo: use specimen pack{" "}
        <select defaultValue="" onChange={(e) => loadSamplePack(e.target.value)}>
          <option value="">choose K01-K12…</option>
          {demoLeads.map((l) => <option key={l.applicant} value={l.applicant}>{l.applicant} · {l.business_name}</option>)}
        </select>
      </div>
      <div className="slots">
        {slots.map((slot) => {
          const r = results[slot];
          return (
            <div className="slot" key={slot}>
              <h4>{SLOTS[slot]} <Verdict value={reading[slot] ? "READING" : r ? r.verdict : "MISSING"} /></h4>
              <input type="file" accept="image/png,image/jpeg"
                onChange={(e) => e.target.files[0] && upload(slot, e.target.files[0])} />
              {r && <><Findings findings={r.findings} /><Fields fields={r.fields} /></>}
            </div>
          );
        })}
      </div>
      {error && <Result kind="bad" lines={[error]} />}
      <div className="actions">
        <button disabled={Object.values(reading).some(Boolean)} onClick={submit}>Submit documents</button>
      </div>
      {k && (k.verdict === "PASS"
        ? <Result kind="ok" title="All documents verified." lines={["Your order is placed."]} />
        : <Result kind={k.verdict === "REJECT" ? "bad" : "warn"}
            title={k.verdict === "REJECT" ? "We can't accept these documents:" : "Almost there - please fix:"} lines={issues} />)}
    </div>
  );
}
