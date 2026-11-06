"""Funnel analysis of smb_leads.csv and a replay of past sales through the rules engine."""
import collections

from . import advisor

FUNNEL = ["Lead", "Contacted", "Needs assessed", "Quote accepted", "KYC complete", "Activated"]
FIXED_BY = {
    "Owner had no time for a visit": "Self-serve advisor (no visit)",
    "Visit not scheduled by sales": "Self-serve advisor (no visit)",
    "Quote too complex to understand": "3-option instant quote",
    "Quote took too long to arrive": "3-option instant quote",
    "Price too high": "3-option instant quote",
    "Missing GST or Udyam document": "Registry lookup + Smart KYC",
    "Found paperwork too long": "Registry lookup + Smart KYC",
    "Document details did not match": "Registry lookup + Smart KYC",
    "Authorised signatory not available": "Registry lookup + Smart KYC",
    "Installation delayed beyond 21 days": "Order tracker + escalation",
    "Site not feasible for fibre": "Feasibility check before quote",
}


def compute(reg):
    leads = list(reg.leads.values())
    reached = collections.Counter()
    for l in leads:
        for s in FUNNEL[:FUNNEL.index(l["stage_reached"]) + 1]:
            reached[s] += 1
    drops = collections.Counter((l["stage_reached"], l["drop_reason"]) for l in leads if l["outcome"] == "Dropped")

    bad_gst, violations = [], collections.Counter()
    for l in leads:
        if l["outcome"] != "Activated":
            continue
        g = reg.gst.get(l["gstin"])
        if g and g["status"] != "Active":
            bad_gst.append(g["status"])
        items = [{"product_id": b.split("x")[0]} for b in l["bundle_products"].split(";")]
        profile = advisor.profile_from_lead(l, bool(g) and g["status"] == "Active")
        for v in advisor.bundle_violations(items, profile, reg.products):
            violations[v["reason"].split(" - ")[0]] += 1

    activated = [l for l in leads if l["outcome"] == "Activated"]
    by_calls = collections.defaultdict(list)
    for l in activated:
        by_calls[min(int(l["customer_follow_up_calls"]), 5)].append(int(l["nps_score"]))
    return {
        "funnel": [{"stage": s, "leads": reached[s]} for s in FUNNEL],
        "drops": [{"stage": s, "reason": r, "leads": n, "fixed_by": FIXED_BY.get(r)}
                  for (s, r), n in drops.most_common()],
        "replay": {"activated_with_inactive_gstin": len(bad_gst),
                   "inactive_breakdown": dict(collections.Counter(bad_gst)),
                   "bundle_rule_violations": sum(violations.values()),
                   "violation_breakdown": dict(violations)},
        "nps_by_follow_up_calls": [{"calls": "%d%s" % (k, "+" if k == 5 else ""), "customers": len(v),
                                    "nps": round(sum(v) / len(v), 1)} for k, v in sorted(by_calls.items())],
        "avg_days_to_activate": round(sum(int(l["days_lead_to_activation"]) for l in activated) / len(activated), 1),
    }
