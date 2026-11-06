import { api, inr } from "../api.js";

export default function TrackStep({ app, setApp }) {
  const { stages, order, notifications } = app.tracker;
  const advance = async () => setApp(await api(`applications/${app.id}/advance`, {}));

  return (
    <div className="step">
      <h2>Track your connection</h2>
      <div className="grid2">
        <div>
          <div className="card">
            <b>{app.business.trade_name}</b> · {app.business.gstin}<br />
            {inr(app.quote.monthly_total)}/month · {app.quote.term_months} months<br />
            <span className="muted">Expected live by</span> <b>{order.activate_by}</b>
          </div>
          <ul className="timeline">
            {stages.map((s) => (
              <li key={s.key} className={s.done ? "done" : ""}>
                {s.label}{s.on && <span className="muted"> · {s.on}</span>}
              </li>
            ))}
          </ul>
          <table>
            <thead><tr><th>Product</th><th>Ready by</th></tr></thead>
            <tbody>{order.per_product.map((p) => <tr key={p.product_name}><td>{p.product_name}</td><td>{p.ready_by}</td></tr>)}</tbody>
          </table>
        </div>
        <div>
          <h3>Messages to customer (WhatsApp)</h3>
          <div className="msgs">
            {notifications.map((n, i) => <div className="msg" key={i}><small>{n.on}</small>{n.text}</div>)}
          </div>
        </div>
      </div>
      <div className="actions">
        <button className="secondary" disabled={app.stage === "ACTIVATED"} onClick={advance}>Simulate next event (demo)</button>
      </div>
    </div>
  );
}
