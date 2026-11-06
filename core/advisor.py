"""Needs advisor: catalogue eligibility rules, 3-tier bundle recommendation and pricing."""
import math

SEGMENTS = {
    "Micro retail & services": "micro",
    "Professional offices": "prof",
    "Small multi-site businesses": "multi",
    "Small manufacturers": "mfg",
}
TERMS = (12, 24)
FIBRE = ("P01", "P02", "P03", "P05", "P06")


def ineligible_reason(p, profile):
    """None if product p can be sold to this profile, else a customer-readable reason."""
    if str(profile["city_tier"]) not in p["available_city_tiers"].split(";"):
        return "not sold in tier-%s cities" % profile["city_tier"]
    if profile["employees"] < int(p["min_employees"]):
        return "needs at least %s employees" % p["min_employees"]
    if profile["sites"] < int(p["min_sites"]):
        return "needs at least %s sites" % p["min_sites"]
    if p["requires_gstin"] == "Y" and not profile["gstin_active"]:
        return "needs an active GSTIN"
    if not profile.get("fibre_feasible", True) and p["product_id"] in FIBRE:
        return "fibre is not available at this address"
    return None


def default_qty(p, profile):
    e, s = profile["employees"], profile["sites"]
    return {
        "per site": s, "per line": max(1, min(e, 2 * s)), "per user": e,
        "per device": 2 * s if p["category"] == "IoT & Physical" else e,
        "per camera": 2 * s, "per counter": s, "per channel": 2, "per vehicle": 1,
    }.get(p["unit"], 1)


def bundle_violations(items, profile, products):
    """Every catalogue rule the bundle breaks: [{product_id, reason}]."""
    ids = {i["product_id"] for i in items}
    out = []
    for i in items:
        p = products[i["product_id"]]
        reason = ineligible_reason(p, profile)
        if not reason and p["requires_one_of"] and not ids & set(p["requires_one_of"].split("|")):
            names = " or ".join(products[x]["product_name"] for x in p["requires_one_of"].split("|"))
            reason = "must be bought with " + names
        if reason:
            out.append({"product_id": p["product_id"], "product_name": p["product_name"], "reason": reason})
    return out


def _first_eligible(ids, profile, products):
    return next((i for i in ids if not ineligible_reason(products[i], profile)), None)


def _resolve(ids, profile, products):
    """Keep eligible products, add the cheapest eligible base for any dependency, de-duplicate."""
    chosen, dropped = [], []
    for i in filter(None, ids):
        if i in chosen:
            continue
        reason = ineligible_reason(products[i], profile)
        if reason:
            dropped.append({"product_id": i, "product_name": products[i]["product_name"], "reason": reason})
            continue
        dep = products[i]["requires_one_of"]
        if dep and not set(chosen) & set(dep.split("|")):
            base = _first_eligible(sorted(dep.split("|"), key=lambda x: int(products[x]["price_min_inr_per_month"])),
                                   profile, products)
            if not base:
                dropped.append({"product_id": i, "product_name": products[i]["product_name"],
                                "reason": "no eligible connection to attach it to"})
                continue
            chosen.insert(0, base)
        chosen.append(i)
    return chosen, dropped


def recommend(profile, products):
    seg, e, s = profile["segment"], profile["employees"], profile["sites"]
    no_fibre = not profile.get("fibre_feasible", True)

    def conn(order):
        return "P04" if no_fibre else _first_eligible(order, profile, products)

    essential = [conn(["P01"]), "P07"]
    core = {"micro": ["P01"], "prof": ["P02", "P01"], "multi": ["P02", "P01"], "mfg": ["P05", "P02", "P01"]}[seg]
    popular_addon = {"micro": ["P19"]}.get(seg, [])     # most-bought add-on for micro in smb_leads (P01+P07+P19)
    recommended = [conn(core), "P07"] + popular_addon + profile.get("interests", [])
    upgrade = {"mfg": ["P06", "P05", "P02", "P01"] if e >= 25 else ["P05", "P02", "P01"]}.get(seg, ["P03", "P02", "P01"])
    complete = [conn(upgrade), "P07"] \
        + profile.get("interests", [])
    complete += {"micro": ["P22", "P19", "P23"], "prof": ["P09", "P16", "P20"],
                 "multi": ["P09", "P10", "P21", "P16"], "mfg": ["P09", "P21", "P24", "P20"]}[seg]
    if s >= 3:
        complete.append("P10")

    tiers, ineligible = [], {}
    for name, ids in (("Essential", essential), ("Recommended", recommended), ("Complete", complete)):
        chosen, dropped = _resolve(ids, profile, products)
        for d in dropped:
            ineligible[d["product_id"]] = d
        items = [{"product_id": i, "qty": default_qty(products[i], profile)} for i in chosen]
        tiers.append(dict(name=name, **price(items, 12, products)))
    return {"tiers": tiers, "ineligible": list(ineligible.values())}


def price(items, term, products):
    """Price within the catalogue range: longer commitment -> closer to the minimum price."""
    term = max([term] + [int(products[i["product_id"]]["min_contract_months"]) for i in items])
    f = 0.0 if term >= 24 else 0.5
    lines, monthly, setup = [], 0, 0
    for i in items:
        p = products[i["product_id"]]
        lo, hi = int(p["price_min_inr_per_month"]), int(p["price_max_inr_per_month"])
        unit = int(math.ceil((lo + (hi - lo) * f) / 10.0) * 10) if lo != hi else lo
        qty = max(1, int(i["qty"]))
        lines.append({"product_id": p["product_id"], "product_name": p["product_name"], "category": p["category"],
                      "description": p["description"], "unit": p["unit"], "qty": qty, "unit_price": unit,
                      "monthly": unit * qty, "setup": int(p["one_time_setup_inr"]) * qty,
                      "install_days": int(p["typical_install_days"])})
        monthly += unit * qty
        setup += int(p["one_time_setup_inr"]) * qty
    return {"items": lines, "monthly_total": monthly, "setup_total": setup, "term_months": term,
            "install_days": max([l["install_days"] for l in lines] or [0])}


def profile_from_lead(lead, gst_active):
    return {
        "segment": SEGMENTS[lead["segment"]], "city_tier": int(lead["city_tier"]),
        "employees": int(lead["employee_count"]), "sites": int(lead["num_sites"]),
        "gstin_active": gst_active, "fibre_feasible": True,
        "interests": [x for x in lead["products_of_interest"].split(";") if x],
    }
