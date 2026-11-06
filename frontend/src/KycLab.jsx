import { useEffect, useState } from "react";
import { api, SLOTS } from "./api.js";
import { Fields, Findings, Verdict } from "./components/ui.jsx";

export default function KycLab({ demoLeads }) {
  const [results, setResults] = useState({});
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let live = true;
    (async () => {
      for (const l of demoLeads) {
        const r = await api("kyc-lab/" + l.applicant);
        if (live) setResults((x) => ({ ...x, [l.applicant]: r }));
      }
    })();
    return () => { live = false; };
  }, [demoLeads]);

  const r = selected && results[selected];

  return (
    <section>
      <h2>Smart KYC lab</h2>
      <p className="muted">Runs every specimen pack (K01-K12) through OCR and the KYC rules. "Today" is 2026-07-15.</p>
      <div className="labgrid">
        {demoLeads.map((l) => (
          <div key={l.applicant} className={`labcard ${selected === l.applicant ? "on" : ""}`} onClick={() => setSelected(l.applicant)}>
            <b>{l.applicant}</b>{l.business_name}<br /><span className="muted">{l.city}</span>
            <div>{results[l.applicant] ? <Verdict value={results[l.applicant].verdict} /> : <Verdict value="READING" />}</div>
          </div>
        ))}
      </div>
      {r && (
        <div className="card">
          <h3>{selected} · {r.business} <Verdict value={r.verdict} /></h3>
          <span className="muted">{r.constitution} · GST registry status: {r.gst_status}</span>
          <div className="thumbs">
            {Object.keys(SLOTS).filter((s) => r.documents[s]?.fields && Object.keys(r.documents[s].fields).length).map((s) => (
              <a key={s} href={`/samples/${selected}_${s}.png`} target="_blank" rel="noreferrer">
                <img src={`/samples/${selected}_${s}.png`} alt={SLOTS[s]} />
              </a>
            ))}
          </div>
          <div className="slots">
            {Object.entries(r.documents).map(([s, d]) => (
              <div className="slot" key={s}>
                <h4>{d.label} <Verdict value={d.verdict} /></h4>
                <Findings findings={d.findings} />
                <Fields fields={d.fields} />
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
