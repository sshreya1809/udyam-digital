"""Mock GST / Udyam registries, leads and product catalogue, loaded from data/*.csv."""
import csv
import os
import re

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
UDYAM_RE = re.compile(r"^UDYAM-([A-Z]{2})-(\d{2})-(\d{7})$")


def _load(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gstin_check_char(first14):
    total = 0
    for i, c in enumerate(first14):
        p = ALNUM.index(c) * (2 if i % 2 else 1)
        total += p // 36 + p % 36
    return ALNUM[(36 - total % 36) % 36]


def gstin_format_errors(g):
    """Offline structure check. Empty list means the GSTIN is well-formed."""
    if not GSTIN_RE.match(g):
        return ["GSTIN must be 15 characters: 2-digit state code, 10-character PAN, entity number, 'Z', check digit"]
    if gstin_check_char(g[:14]) != g[14]:
        return ["GSTIN check digit is wrong - please re-check the number"]
    return []


def mask(identifier):
    """27QTBXZ1995X1Z9 -> 27QTB•••••••1Z9 ; UDYAM-MH-00-7656096 -> UDYAM-MH-00-•••6096"""
    if not identifier:
        return ""
    if identifier.startswith("UDYAM-"):
        return identifier[:12] + "•••" + identifier[-4:]
    return identifier[:5] + "•" * (len(identifier) - 8) + identifier[-3:]


class Registry:
    def __init__(self):
        self.gst = {r["gstin"]: r for r in _load("mock_gstin_registry.csv")}
        self.udyam = {r["udyam_number"]: r for r in _load("mock_udyam_registry.csv")}
        self.leads = {r["lead_id"]: r for r in _load("smb_leads.csv")}
        self.products = {r["product_id"]: r for r in _load("product_catalogue.csv")}
        self.gst_state = {g[:2]: r["state"] for g, r in self.gst.items()}
        self.udyam_state = {UDYAM_RE.match(u).group(1): r["state"] for u, r in self.udyam.items()}

    def lookup_gstin(self, gstin):
        g = (gstin or "").strip().upper()
        errors = gstin_format_errors(g)
        if errors:
            return {"ok": False, "errors": errors}
        if g[:2] not in self.gst_state:
            return {"ok": False, "errors": [f"State code {g[:2]} is not a recognised GST state code"]}
        rec = self.gst.get(g)
        if not rec:
            return {"ok": False, "errors": ["GSTIN not found in the GST registry"]}
        if rec["status"] != "Active":
            return {"ok": False, "record": rec,
                    "errors": [f"GSTIN is {rec['status']} - only an Active GSTIN can be used"]}
        return {"ok": True, "record": rec, "errors": []}

    def lookup_udyam(self, number, gst_record=None):
        u = (number or "").strip().upper()
        m = UDYAM_RE.match(u)
        if not m:
            return {"ok": False, "errors": ["Udyam number must look like UDYAM-XX-00-1234567"]}
        rec = self.udyam.get(u)
        if not rec:
            return {"ok": False, "errors": ["Udyam number not found in the Udyam registry"]}
        errors = []
        if gst_record and rec["state"] != gst_record["state"]:
            errors.append(f"Udyam is registered in {rec['state']} but GSTIN is in {gst_record['state']}")
        if gst_record and not same_business(rec["enterprise_name"], gst_record["trade_name"]):
            errors.append("Udyam enterprise name does not match the GST trade name")
        return {"ok": not errors, "record": rec, "errors": errors}


def norm_name(s):
    s = s.lower().replace("&", " and ")
    s = re.sub(r"\b(private|pvt)\b\.?", "pvt", s)
    s = re.sub(r"\b(limited|ltd)\b\.?", "ltd", s)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())


def same_business(a, b):
    return norm_name(a) == norm_name(b)


REGISTRY = None


def get():
    global REGISTRY
    if REGISTRY is None:
        REGISTRY = Registry()
    return REGISTRY
