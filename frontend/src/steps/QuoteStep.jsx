import { useEffect, useState } from "react";
import { api, inr } from "../api.js";
import { Result } from "../components/ui.jsx";

export default function QuoteStep({ products, profile, business, onBack, onAccepted }) {
  const [advice, setAdvice] = useState(null);
  const [picked, setPicked] = useState(null);
  const [items, setItems] = useState([]);
  const [term, setTerm] = useState(12);
  const [quote, setQuote] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { api("advise", { profile }).then(setAdvice, (e) => setError(e.message)); }, [profile]);

  useEffect(() => {
    if (!items.length) { setQuote(null); return; }
    api("quote", { profile, items, term }).then(setQuote, (e) => setError(e.message));
  }, [profile, items, term]);

  const pick = (i) => {
    setPicked(i);
    setItems(advice.tiers[i].items.map((x) => ({ product_id: x.product_id, qty: x.qty })));
  };
  const setQty = (i, qty) => setItems((xs) => xs.map((x, j) => (j === i ? { ...x, qty: Math.max(1, qty) } : x)));
  const remove = (i) => setItems((xs) => xs.filter((_, j) => j !== i));
  const add = (id) => id && !items.some((x) => x.product_id === id) && setItems((xs) => [...xs, { product_id: id, qty: 1 }]);

  async function accept() {
    try {
      onAccepted(await api("applications", { gstin: business.gstin, udyam_number: business.udyam, profile, items, term }));
    } catch (e) { setError(e.message); }
  }

  if (!advice) return <div className="step">{error ? <Result kind="bad" lines={[error]} /> : "Finding your options…"}</div>;

  return (
    <div className="step">
      <h2>Pick an option</h2>
      <div className="tiers">
        {advice.tiers.map((t, i) => (
          <div key={t.name} className={`tier ${i === 1 ? "recommended" : ""} ${picked === i ? "on" : ""}`} onClick={() => pick(i)}>
            <div>{t.name} {i === 1 && <span className="badge-rec">Best fit</span>}</div>
            <div className="price">{inr(t.monthly_total)}<small>/month</small></div>
            <div className="muted">{t.setup_total ? `${inr(t.setup_total)} one-time setup` : "No setup fee"} · live in ~{t.install_days} days</div>
            <ul>{t.items.map((x) => <li key={x.product_id}>{x.product_name}{x.qty > 1 ? ` × ${x.qty}` : ""}</li>)}</ul>
          </div>
        ))}
      </div>
      {advice.ineligible.length > 0 && (
        <Result kind="warn" title="Not available for you yet:"
          lines={advice.ineligible.map((x) => `${x.product_name} — ${x.reason}`)}>
          {!business.gstin && <div className="muted">Register for GST to unlock these.</div>}
        </Result>
      )}

      {quote && (
        <>
          <h3>Your quote</h3>
          <div className="row">
            <label>Contract
              <select value={term} onChange={(e) => setTerm(+e.target.value)}>
                <option value={12}>12 months</option><option value={24}>24 months (lower price)</option>
              </select>
            </label>
            <label>Add product
              <select value="" onChange={(e) => add(e.target.value)}>
                <option value="">choose…</option>
                {products.map((p) => <option key={p.product_id} value={p.product_id}>{p.product_name} ({p.category})</option>)}
              </select>
            </label>
          </div>
          {quote.term_months > term && (
            <p className="muted">Some products in this bundle need a {quote.term_months}-month minimum contract.</p>
          )}
          <table>
            <thead><tr><th>Product</th><th>Unit</th><th>Qty</th><th>Price</th><th>Monthly</th><th>Setup</th><th /></tr></thead>
            <tbody>
              {quote.items.map((x, i) => (
                <tr key={x.product_id}>
                  <td><b>{x.product_name}</b><br /><span className="muted">{x.description}</span></td>
                  <td>{x.unit}</td>
                  <td><input type="number" min={1} value={x.qty} onChange={(e) => setQty(i, +e.target.value)} /></td>
                  <td>{inr(x.unit_price)}</td><td>{inr(x.monthly)}</td><td>{x.setup ? inr(x.setup) : "-"}</td>
                  <td><button className="x" title="Remove" onClick={() => remove(i)}>✕</button></td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={4}>Total · {quote.term_months}-month contract · live in ~{quote.install_days} days</td>
                <td>{inr(quote.monthly_total)}/mo</td><td>{inr(quote.setup_total)}</td><td />
              </tr>
            </tfoot>
          </table>
          {quote.violations.length > 0 && (
            <Result kind="bad" title="This bundle can't be sold as is:"
              lines={quote.violations.map((v) => `${v.product_name} — ${v.reason}`)} />
          )}
        </>
      )}
      {error && <Result kind="bad" lines={[error]} />}
      <div className="actions">
        <button className="secondary" onClick={onBack}>Back</button>
        <button disabled={!quote || quote.violations.length > 0 || !business.gstin}
          title={business.gstin ? "" : "A verified GSTIN is needed to continue online"} onClick={accept}>
          Accept quote
        </button>
      </div>
    </div>
  );
}
