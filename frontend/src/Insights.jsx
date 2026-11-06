import { useEffect, useState } from "react";
import { api } from "./api.js";

export default function Insights() {
  const [d, setD] = useState(null);
  useEffect(() => { api("insights").then(setD); }, []);
  if (!d) return <p>Loading…</p>;

  const max = d.funnel[0].leads;
  const fixable = d.drops.filter((x) => x.fixed_by).reduce((a, x) => a + x.leads, 0);

  return (
    <section>
      <h2>Why the funnel leaks - and what each module fixes</h2>
      <div className="kpis">
        <div className="kpi"><b>{d.funnel.at(-1).leads} / {max}</b>leads activated (Apr-Jun 2026), avg {d.avg_days_to_activate} days</div>
        <div className="kpi"><b>{fixable.toLocaleString("en-IN")}</b>lost leads whose drop reason a module here removes</div>
        <div className="kpi">
          <b>{d.replay.activated_with_inactive_gstin} + {d.replay.bundle_rule_violations}</b>
          activations on a cancelled/suspended GSTIN + sold bundle lines breaking catalogue rules — blocked by the rules engine
        </div>
      </div>
      <div className="card">
        <h3>Funnel</h3>
        <div className="bars">
          {d.funnel.map((f) => (
            <div className="bar" key={f.stage}>
              <span>{f.stage}</span>
              <span className="fill" style={{ width: `${(f.leads / max) * 600}px` }} />
              <span>{f.leads}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="card">
        <h3>Drop reasons</h3>
        <table>
          <thead><tr><th>Stage</th><th>Reason</th><th>Leads</th><th>Fixed by</th></tr></thead>
          <tbody>
            {d.drops.map((x) => (
              <tr key={x.stage + x.reason}>
                <td>{x.stage}</td><td>{x.reason}</td><td>{x.leads}</td>
                <td>{x.fixed_by || <span className="muted">sales / out of scope</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <h3>Customers who chase us are less happy</h3>
        <table>
          <thead><tr><th>Follow-up calls</th><th>Customers</th><th>NPS</th></tr></thead>
          <tbody>{d.nps_by_follow_up_calls.map((x) => <tr key={x.calls}><td>{x.calls}</td><td>{x.customers}</td><td>{x.nps}</td></tr>)}</tbody>
        </table>
        <p className="muted">Hence proactive WhatsApp updates at every order step.</p>
      </div>
    </section>
  );
}
