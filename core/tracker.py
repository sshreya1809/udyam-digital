"""Order tracker: stages, expected dates from typical_install_days, proactive customer updates."""
import datetime

from .kyc import TODAY

STAGES = [
    ("QUOTE_ACCEPTED", "Quote accepted"),
    ("KYC_VERIFIED", "KYC verified"),
    ("INSTALL_SCHEDULED", "Installation scheduled"),
    ("INSTALLED", "Installed"),
    ("ACTIVATED", "Activated"),
]
LABEL = dict(STAGES)
ESCALATE_AFTER_DAYS = 21


def _d(s):
    return datetime.date.fromisoformat(s)


def start_order(app):
    """On KYC pass: plan installation from the slowest product in the bundle."""
    install_days = app["quote"]["install_days"]
    app["order"] = {
        "kyc_date": TODAY.isoformat(),
        "install_by": (TODAY + datetime.timedelta(days=install_days)).isoformat(),
        "activate_by": (TODAY + datetime.timedelta(days=install_days + 1)).isoformat(),
        "per_product": [{"product_name": i["product_name"],
                         "ready_by": (TODAY + datetime.timedelta(days=i["install_days"])).isoformat()}
                        for i in app["quote"]["items"]],
    }
    move(app, "KYC_VERIFIED")


def move(app, stage, on=None):
    on = on or TODAY.isoformat()
    app["stage"] = stage
    app["history"].append({"stage": stage, "label": LABEL[stage], "on": on})
    notify(app, _message(app, stage))


def advance(app):
    """Demo-only: simulate the next operational event."""
    keys = [k for k, _ in STAGES]
    i = keys.index(app["stage"])
    if i + 1 >= len(keys):
        return
    nxt = keys[i + 1]
    order = app["order"]
    on = {"INSTALL_SCHEDULED": order["kyc_date"], "INSTALLED": order["install_by"],
          "ACTIVATED": order["activate_by"]}.get(nxt)
    move(app, nxt, on)


def _message(app, stage):
    name = app["business"]["trade_name"]
    o = app.get("order", {})
    return {
        "QUOTE_ACCEPTED": "Hi %s, your quote of Rs %s/month is confirmed. Next: upload 3-4 documents (5 minutes)."
                          % (name, app["quote"]["monthly_total"]),
        "KYC_VERIFIED": "Documents verified. Installation expected by %s - we will message you at every step."
                        % o.get("install_by"),
        "INSTALL_SCHEDULED": "Engineer visit booked. Expected install date: %s." % o.get("install_by"),
        "INSTALLED": "Installation done. Your services go live by %s." % o.get("activate_by"),
        "ACTIVATED": "You are live! Reply HELP any time for support.",
    }[stage]


def notify(app, text):
    """Prototype: record the WhatsApp/SMS that would be sent."""
    app["notifications"].append({"on": app["history"][-1]["on"] if app["history"] else TODAY.isoformat(),
                                 "channel": "WhatsApp", "text": text})


def view(app):
    reached = {h["stage"]: h["on"] for h in app["history"]}
    o = app.get("order")
    late = bool(o) and app["stage"] != "ACTIVATED" and (TODAY - _d(o["kyc_date"])).days > ESCALATE_AFTER_DAYS
    return {"stages": [{"key": k, "label": l, "on": reached.get(k), "done": k in reached} for k, l in STAGES],
            "order": o, "escalate": late, "notifications": app["notifications"]}
