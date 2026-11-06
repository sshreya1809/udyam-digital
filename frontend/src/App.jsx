import { useEffect, useState } from "react";
import { api } from "./api.js";
import Journey from "./Journey.jsx";
import KycLab from "./KycLab.jsx";
import Insights from "./Insights.jsx";

const TABS = [["journey", "Get connected"], ["lab", "KYC Lab"], ["insights", "Insights"]];

export default function App() {
  const [tab, setTab] = useState("journey");
  const [catalogue, setCatalogue] = useState({ products: [], demoLeads: [] });

  useEffect(() => {
    Promise.all([api("products"), api("demo-leads")])
      .then(([products, demoLeads]) => setCatalogue({ products, demoLeads }));
  }, []);

  return (
    <>
      <header>
        <div className="brand">Accel Business <span>Udyam Digital</span></div>
        <nav>
          {TABS.map(([key, label]) => (
            <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>{label}</button>
          ))}
        </nav>
      </header>
      <main>
        {/* Journey stays mounted so switching tabs doesn't lose the customer's progress */}
        <div hidden={tab !== "journey"}><Journey {...catalogue} /></div>
        {tab === "lab" && <KycLab demoLeads={catalogue.demoLeads} />}
        {tab === "insights" && <Insights />}
      </main>
    </>
  );
}
