import { useState } from "react";
import BusinessStep from "./steps/BusinessStep.jsx";
import NeedsStep from "./steps/NeedsStep.jsx";
import QuoteStep from "./steps/QuoteStep.jsx";
import KycStep from "./steps/KycStep.jsx";
import TrackStep from "./steps/TrackStep.jsx";

const STEPS = ["Business", "Needs", "Quote", "Documents", "Track"];

export default function Journey({ products, demoLeads }) {
  const [step, setStep] = useState(1);
  const [business, setBusiness] = useState({ gstin: null, udyam: "", lead: null });
  const [profile, setProfile] = useState(null);
  const [app, setApp] = useState(null);

  return (
    <section>
      <ol className="stepper">
        {STEPS.map((s, i) => (
          <li key={s} className={i + 1 === step ? "active" : i + 1 < step ? "done" : ""}>{s}</li>
        ))}
      </ol>
      {step === 1 && <BusinessStep demoLeads={demoLeads} value={business} onDone={(b) => { if (b.lead?.lead_id !== business.lead?.lead_id) setProfile(null); setBusiness(b); setStep(2); }} />}
      {step === 2 && (
        <NeedsStep products={products} lead={business.lead} gstinActive={!!business.gstin}
          initial={profile} onBack={() => setStep(1)} onDone={(p) => { setProfile(p); setStep(3); }} />
      )}
      {step === 3 && (
        <QuoteStep products={products} profile={profile} business={business}
          onBack={() => setStep(2)} onAccepted={(a) => { setApp(a); setStep(4); }} />
      )}
      {step === 4 && <KycStep app={app} setApp={setApp} demoLeads={demoLeads} onVerified={() => setStep(5)} />}
      {step === 5 && <TrackStep app={app} setApp={setApp} />}
    </section>
  );
}
