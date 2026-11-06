"""Udyam Digital prototype server. Standard library only; listens on loopback."""
import base64
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from core import advisor, insights, kyc, registry, store, tracker

HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8000"))
ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "frontend", "dist")          # React build (npm run build)
SAMPLES = os.path.join(ROOT, "data", "kyc_documents")
MAX_BODY = 8 * 1024 * 1024
TYPES = {".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".svg": "image/svg+xml",
         ".png": "image/png", ".ico": "image/x-icon"}
SAMPLE_RE = re.compile(r"^/samples/(K\d{2}_(gst_certificate|udyam_certificate|signatory_id|address_proof))\.png$")
ID_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b|UDYAM-[A-Z]{2}-\d{2}-\d{7}")

REG = registry.get()
INSIGHTS = insights.compute(REG)
WRITE_LOCK = threading.Lock()   # application updates are load-modify-save; serialise them
APPLICANTS = json.load(open(os.path.join(ROOT, "data", "kyc_applicants.json")))


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def _profile(p):
    try:
        prof = {"segment": p["segment"], "city_tier": int(p["city_tier"]), "employees": int(p["employees"]),
                "sites": int(p["sites"]), "gstin_active": bool(p.get("gstin_active")),
                "fibre_feasible": bool(p.get("fibre_feasible", True)),
                "interests": [i for i in p.get("interests", []) if i in REG.products]}
    except (KeyError, TypeError, ValueError):
        raise ApiError(400, "profile needs segment, city_tier, employees, sites")
    if prof["segment"] not in advisor.SEGMENTS.values() or prof["city_tier"] not in (1, 2) \
            or prof["employees"] < 1 or prof["sites"] < 1:
        raise ApiError(400, "invalid profile values")
    return prof


def _items(raw):
    items = [{"product_id": i["product_id"], "qty": int(i.get("qty", 1))} for i in raw or []
             if i.get("product_id") in REG.products]
    if not items:
        raise ApiError(400, "quote needs at least one product")
    return items


def _quote(body):
    prof = _profile(body.get("profile", {}))
    items = _items(body.get("items"))
    term = int(body.get("term", 12))
    if term not in advisor.TERMS:
        raise ApiError(400, "term must be one of %s" % (advisor.TERMS,))
    q = advisor.price(items, term, REG.products)
    q["violations"] = advisor.bundle_violations(items, prof, REG.products)
    return prof, q


def _app_or_404(app_id):
    app = store.load(app_id)
    if not app:
        raise ApiError(404, "application not found")
    return app


def _kyc_context(app):
    b = app["business"]
    return {"gst": REG.gst[b["gstin"]], "udyam_number": b.get("udyam_number", ""),
            "udyam": REG.udyam.get(b.get("udyam_number", ""))}


def _public(app):
    """Customer-facing view: identifiers masked, no raw document fields."""
    b = dict(app["business"], gstin=registry.mask(app["business"]["gstin"]),
             udyam_number=registry.mask(app["business"].get("udyam_number", "")))
    return {"id": app["id"], "stage": app["stage"], "business": b, "quote": app["quote"],
            "consent": app.get("consent"), "uploaded": sorted(app.get("docs", {})),
            "required_documents": kyc.required_slots(dict(_kyc_context(app), udyam_uploaded="udyam_certificate" in app.get("docs", {}))),
            "kyc": app.get("kyc"), "tracker": tracker.view(app), "audit": store.audit_log(app["id"])}


def _lookup_gstin(g):
    r = REG.lookup_gstin(g)
    rec = r.get("record")
    if rec:
        r["record"] = {k: rec[k] for k in ("legal_name", "trade_name", "constitution",
                                           "principal_place_of_business", "state", "status")}
    return r


def route(method, path, query, body):
    parts = [p for p in path.split("/") if p][1:]          # strip "api"
    if method == "GET" and parts[:1] == ["gstin"] and len(parts) == 2:
        return _lookup_gstin(parts[1])
    if method == "GET" and parts[:1] == ["udyam"] and len(parts) == 2:
        gst = REG.gst.get(query.get("gstin", [""])[0].upper())
        return REG.lookup_udyam(parts[1], gst)
    if method == "GET" and parts == ["products"]:
        return list(REG.products.values())
    if method == "GET" and parts == ["insights"]:
        return INSIGHTS
    if method == "GET" and parts == ["demo-leads"]:
        return [{"applicant": k, "lead_id": v, "business_name": REG.leads[v]["business_name"],
                 "city": REG.leads[v]["city"]} for k, v in APPLICANTS.items()]
    if method == "GET" and parts[:1] == ["leads"] and len(parts) == 2:
        lead = REG.leads.get(parts[1])
        if not lead:
            raise ApiError(404, "lead not found")
        g = REG.gst.get(lead["gstin"])
        prof = advisor.profile_from_lead(lead, bool(g) and g["status"] == "Active")
        return {"lead_id": lead["lead_id"], "business_name": lead["business_name"], "gstin": lead["gstin"],
                "udyam_number": lead["udyam_number"], "city": lead["city"], "profile": prof,
                "current_spend": int(lead["monthly_telecom_spend_inr"] or 0)}
    if method == "POST" and parts == ["advise"]:
        return advisor.recommend(_profile(body.get("profile", {})), REG.products)
    if method == "POST" and parts == ["quote"]:
        return _quote(body)[1]

    if method == "POST" and parts == ["applications"]:
        prof, q = _quote(body)
        if q["violations"]:
            raise ApiError(422, "bundle breaks catalogue rules: " + "; ".join(
                "%s %s" % (v["product_name"], v["reason"]) for v in q["violations"]))
        g = REG.lookup_gstin(body.get("gstin", ""))
        if not g["ok"]:
            raise ApiError(422, " ".join(g["errors"]))
        rec = g["record"]
        udyam = (body.get("udyam_number") or "").strip().upper()
        if udyam:
            u = REG.lookup_udyam(udyam, rec)
            if not u["ok"]:
                raise ApiError(422, " ".join(u["errors"]))
        app = {"id": store.next_id(), "stage": "QUOTE_ACCEPTED", "profile": prof, "quote": q,
               "business": {"gstin": rec["gstin"], "udyam_number": udyam, "trade_name": rec["trade_name"],
                            "legal_name": rec["legal_name"], "constitution": rec["constitution"],
                            "state": rec["state"]},
               "docs": {}, "history": [], "notifications": []}
        tracker.move(app, "QUOTE_ACCEPTED")
        store.save(app)
        store.audit(app["id"], "application created for GSTIN %s" % registry.mask(rec["gstin"]))
        return _public(app)

    if parts[:1] == ["applications"] and len(parts) >= 2:
        app = _app_or_404(parts[1])
        action = parts[2] if len(parts) > 2 else None
        if method == "GET" and action is None:
            return _public(app)
        if method == "POST" and action == "consent":
            if not body.get("accepted"):
                raise ApiError(400, "consent must be accepted to continue")
            app["consent"] = {"version": "kyc-v1", "on": kyc.TODAY.isoformat()}
            store.audit(app["id"], "KYC consent accepted (kyc-v1)")
        elif method == "POST" and action == "documents":
            if not app.get("consent"):
                raise ApiError(403, "accept the KYC consent notice before uploading documents")
            if app["stage"] != "QUOTE_ACCEPTED":
                raise ApiError(409, "KYC already completed")
            slot = body.get("slot")
            if slot not in kyc.DOC_TYPES:
                raise ApiError(400, "unknown document slot")
            try:
                image = base64.b64decode(body.get("image_base64", ""), validate=True)
            except ValueError:
                raise ApiError(400, "image_base64 is not valid base64")
            if not image.startswith(b"\x89PNG") and not image.startswith(b"\xff\xd8"):
                raise ApiError(400, "upload a PNG or JPEG image")
            doc = kyc.extract(kyc.ocr(image))
            app["docs"][slot] = doc
            findings = kyc.check_document(slot, doc, _kyc_context(app))
            store.audit(app["id"], "%s uploaded - %s" % (kyc.DOC_TYPES[slot][1], kyc.verdict(findings)))
            store.save(app)
            return {"slot": slot, "verdict": kyc.verdict(findings), "findings": findings,
                    "fields": kyc.masked_fields(doc["fields"]), "application": _public(app)}
        elif method == "POST" and action == "submit":
            if app["stage"] != "QUOTE_ACCEPTED":
                raise ApiError(409, "KYC already completed")
            result = kyc.evaluate(_kyc_context(app), app["docs"])
            app["kyc"] = dict(result, on=kyc.TODAY.isoformat())
            store.audit(app["id"], "KYC submitted - %s" % result["verdict"])
            if result["verdict"] == "PASS":
                app["docs"] = {}                     # retention: keep the masked verdict, drop extracted text
                tracker.start_order(app)
        elif method == "POST" and action == "advance":
            if not app.get("order"):
                raise ApiError(409, "order starts after KYC passes")
            tracker.advance(app)
        else:
            raise ApiError(404, "not found")
        store.save(app)
        return _public(app)

    if method == "GET" and parts[:1] == ["kyc-lab"] and len(parts) == 2 and parts[1] in APPLICANTS:
        lead = REG.leads[APPLICANTS[parts[1]]]
        ctx = {"gst": REG.gst[lead["gstin"]], "udyam_number": lead["udyam_number"],
               "udyam": REG.udyam.get(lead["udyam_number"])}
        docs = {}
        for slot in kyc.DOC_TYPES:
            f = os.path.join(SAMPLES, "%s_%s.png" % (parts[1], slot))
            if os.path.exists(f):
                with open(f, "rb") as fh:
                    docs[slot] = kyc.extract(kyc.ocr(fh.read(), cache=True))
        r = kyc.evaluate(ctx, docs)
        r.update(applicant=parts[1], business=lead["business_name"], city=lead["city"],
                 gst_status=ctx["gst"]["status"], constitution=ctx["gst"]["constitution"])
        return r
    raise ApiError(404, "not found")


class Handler(BaseHTTPRequestHandler):
    server_version = "UdyamDigital/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(),
                                      ID_RE.sub(lambda m: registry.mask(m.group(0)), fmt % args)))

    def _send(self, status, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") or "json" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, method):
        url = urlparse(self.path)
        try:
            if method == "GET" and not url.path.startswith(("/api/", "/samples/")):
                return self._static(url.path)
            m = SAMPLE_RE.match(url.path)
            if method == "GET" and m:
                with open(os.path.join(SAMPLES, m.group(1) + ".png"), "rb") as f:
                    return self._send(200, f.read(), "image/png")
            if not url.path.startswith("/api/"):
                raise ApiError(404, "not found")
            body = {}
            if method == "POST":
                n = int(self.headers.get("Content-Length") or 0)
                if n > MAX_BODY:
                    raise ApiError(413, "request too large")
                body = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(body, dict):
                    raise ApiError(400, "JSON object expected")
            if method == "POST":
                with WRITE_LOCK:
                    result = route(method, url.path, parse_qs(url.query), body)
            else:
                result = route(method, url.path, parse_qs(url.query), body)
            self._send(200, result)
        except ApiError as e:
            self._send(e.status, {"error": str(e)})
        except FileNotFoundError:
            self._send(404, {"error": "not found"})
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON"})

    def _static(self, path):
        f = os.path.realpath(os.path.join(DIST, path.lstrip("/") or "index.html"))
        if not f.startswith(os.path.realpath(DIST) + os.sep) or not os.path.isfile(f):
            f = os.path.join(DIST, "index.html")             # single-page app
        with open(f, "rb") as fh:
            self._send(200, fh.read(), TYPES.get(os.path.splitext(f)[1], "application/octet-stream"))

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


if __name__ == "__main__":
    if not os.path.exists(kyc.OCR_BIN):
        sys.exit("OCR helper missing - run ./setup.sh first")
    if not os.path.exists(os.path.join(DIST, "index.html")):
        sys.exit("React build missing - run ./setup.sh first")
    print("Udyam Digital running on http://%s:%d" % (HOST, PORT))
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
