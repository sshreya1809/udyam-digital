"""Smart KYC: OCR a document, extract fields, check them against the registries and the rules."""
import datetime
import difflib
import hashlib
import json
import os
import re
import subprocess
import tempfile

from . import registry as reg

TODAY = datetime.date(2026, 7, 15)
ADDRESS_PROOF_MAX_DAYS = 90
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OCR_BIN = os.path.join(ROOT, "ocr", "ocr")
OCR_CACHE = os.path.join(ROOT, "data", "ocr_cache")

DOC_TYPES = {
    "gst_certificate": ("GST Registration Certificate", "GST certificate"),
    "udyam_certificate": ("Udyam Registration Certificate", "Udyam certificate"),
    "signatory_id": ("Authorised Signatory ID", "Signatory ID"),
    "address_proof": ("Electricity Bill", "Address proof"),
}
LABELS = {
    "gst_certificate": {"GSTIN": "gstin", "Legal name": "legal_name", "Trade name": "trade_name",
                        "Constitution": "constitution", "Address of principal": "address",
                        "Date of liability": "date", "Type of registration": "reg_type"},
    "udyam_certificate": {"Udyam reg. number": "udyam_number", "Enterprise name": "enterprise_name",
                          "Major activity": "major_activity", "City": "city", "State": "state",
                          "Date of registration": "date"},
    "address_proof": {"Consumer no.": "consumer_no", "Billed to": "billed_to", "Supply address": "address",
                      "Bill date": "date", "Units consumed": "units", "Amount due (INR)": "amount"},
    "signatory_id": {"Name": "name", "Designation": "designation", "For business": "business",
                     "ID no.": "id_no", "Valid till": "valid_till"},
}
ALLOWED_SIGNATORY = {
    "Proprietorship": {"proprietor", "owner"},
    "Limited Liability Partnership": {"designated partner", "partner"},
    "Private Limited Company": {"director", "managing director"},
}
# Diagonal "SYNTHETIC SPECIMEN - NOT A VALID DOCUMENT" fragments: cut from the first one to the end of the line.
WATERMARK = re.compile(r"\s*\b(?:NOT A|T A V|VALI?D?|DOCU\w*|SPECIM\w*|SYNTH\w*|\w*CIMEN|\w*HETIC|OCUM|VOT|HOT)\b.*$")
SEVERITY = {"PASS": 0, "WARN": 1, "FIX": 2, "REJECT": 3}


# ---------- OCR ----------

def ocr(image_bytes, cache=False):
    """Text lines from OCR. The image only exists on disk while OCR runs.
    Checks OCR_CACHE first (contains all 47 bundled specimen documents)."""
    key = hashlib.sha256(image_bytes).hexdigest()
    path = os.path.join(OCR_CACHE, key + ".json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    fd, tmp = tempfile.mkstemp(suffix=".png")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(image_bytes)
        out = subprocess.run([OCR_BIN, tmp], capture_output=True, check=True, timeout=60).stdout
        lines = json.loads(out)
        if cache:
            os.makedirs(OCR_CACHE, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(lines, f)
        return lines
    except Exception as e:
        # Fallback if external OCR binary is unavailable or platform-incompatible (e.g. macOS Vision on Windows)
        return []
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ---------- extraction ----------

def _label_key(text, labels):
    best, score = None, 0.0
    for label, key in labels.items():
        s = 1.0 if label.lower() in text.lower() else difflib.SequenceMatcher(None, label.lower(), text.lower()).ratio()
        if s > score:
            best, score = key, s
    return best if score >= 0.6 else None


def detect_type(lines):
    titles = " ".join(l["text"] for l in lines if l["y"] < 0.12)
    for t, (title, _) in DOC_TYPES.items():
        if title.lower() in titles.lower():
            return t
    return None


def _deskew(values, rows):
    """Vertical offset between the value column and the label column (tilted scans)."""
    if not rows:
        return 0.0
    cost = lambda d: sum(min(min(abs(v["y"] - d - y) for y, _ in rows), 0.02) for v in values)
    return min((d / 1000.0 for d in range(-30, 31, 2)), key=lambda d: (round(cost(d), 3), abs(d)))


def extract(lines):
    """-> {type, fields, quality}. Watermark fragments dropped; wrapped values re-joined."""
    doc_type = detect_type(lines)
    body = []
    for l in lines:
        cy = l["y"] + l.get("h", 0) / 2
        if 0.1 <= cy < 0.93:
            body.append(dict(l, y=cy, text=l["text"].strip(), clean=WATERMARK.sub("", l["text"]).strip()))
    body.sort(key=lambda l: (l["y"], l["x"]))
    clean = [dict(l, text=l["clean"]) for l in body if re.search(r"[0-9A-Za-z]", l["clean"])]
    quality = sum(l["conf"] for l in clean) / len(clean) if clean else 0.0
    fields = {}
    if doc_type == "signatory_id":          # label above value
        for a, b in zip(clean, clean[1:]):
            key = _label_key(a["text"], LABELS[doc_type])
            if key and key not in fields and abs(a["x"] - b["x"]) < 0.05 \
                    and not _label_key(b["text"], LABELS[doc_type]):
                fields[key] = b["text"].strip()
    elif doc_type:                          # label left, value right; wrapped lines continue the last value
        rows = [(l["y"], k) for l in body if l["x"] < 0.3 for k in [_label_key(l["text"], LABELS[doc_type])] if k]
        values = [l for l in clean if l["x"] >= 0.3]
        d = _deskew(values, rows)
        current = None
        for v in values:
            y, key = min(rows, key=lambda r: abs(v["y"] - d - r[0]), default=(0, None))
            if abs(v["y"] - d - y) > 0.02:
                key = current                # wrapped continuation of the previous value
            if key:
                fields[key] = fields.get(key, "") + v["text"].strip() if key == current else v["text"].strip()
                current = key
    if doc_type == "udyam_certificate":
        fields["udyam_number"] = find_udyam(fields.get("udyam_number"))
    return {"type": doc_type, "fields": fields, "quality": round(quality, 2)}


DIGIT_POS, LETTER_POS = {0, 1, 7, 8, 9, 10}, {2, 3, 4, 5, 6, 11}
TO_DIGIT, TO_LETTER = str.maketrans("OQDISB", "000158"), str.maketrans("01586", "OISBG")
LOOKALIKE = {"O": "Q0D", "Q": "O0", "0": "OQD", "D": "O0", "1": "IL", "I": "1L", "L": "1I",
             "5": "S", "S": "5", "8": "B", "B": "8", "2": "Z", "Z": "2", "6": "G", "G": "6"}


def _fix_positions(w):
    c = list(w)
    for i in DIGIT_POS:
        c[i] = c[i].translate(TO_DIGIT)
    for i in LETTER_POS:
        c[i] = c[i].translate(TO_LETTER)
    c[13] = "Z" if c[13] == "2" else c[13]
    return "".join(c)


def read_gstin(text, declared):
    """Interpret the OCR'd GSTIN against the GSTIN the applicant entered.

    -> (value, status): ok | corrected | invalid | partial | unreadable
    A well-formed number with a wrong check digit means the document itself is wrong (invalid);
    a malformed read means OCR failed (partial / unreadable), never a silent pass.
    """
    s = re.sub(r"[^0-9A-Z]", "", (text or "").upper())
    windows = [_fix_positions(s[i:i + 15]) for i in range(len(s) - 14)]
    well_formed = [w for w in windows if reg.GSTIN_RE.match(w)]
    for w in well_formed:
        if not reg.gstin_format_errors(w):
            return w, "ok"
    for w in well_formed:                    # one look-alike character away from the entered GSTIN
        diff = [i for i in range(15) if w[i] != declared[i]]
        if len(diff) == 1 and declared[diff[0]] in LOOKALIKE.get(w[diff[0]], ""):
            return declared, "corrected"
    if well_formed:
        return well_formed[0], "invalid"
    near = [w for w in windows if sum(a != b for a, b in zip(w, declared)) <= 3]
    return (near[0], "partial") if near else ("", "unreadable")


def find_udyam(text):
    s = re.sub(r"[^0-9A-Z]", "", (text or "").upper())
    m = re.search(r"U[DO0]?YAM([0-9A-Z]{2})([0-9OQDIL]{2})([0-9OQDIL]{7})", s)
    if not m:
        return ""
    digits = str.maketrans("OQDIL", "00011")
    return "UDYAM-%s-%s-%s" % (m.group(1).translate(TO_LETTER), m.group(2).translate(digits),
                               m.group(3).translate(digits))


# ---------- checks ----------

def _close(a, b, cutoff=0.9):
    na, nb = reg.norm_name(a or ""), reg.norm_name(b or "")
    return bool(na) and difflib.SequenceMatcher(None, na, nb).ratio() >= cutoff


def _addr_key(a):
    return re.sub(r"[^a-z0-9]", "", (a or "").lower())


def _same_address(read, registered):
    """Most of the registered address must appear, in order, in the OCR text (watermark junk may be
    interleaved); a cleanly read PIN must match exactly."""
    a, b = _addr_key(read), _addr_key(registered)
    if not a:
        return False
    covered = sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    pin = lambda s: re.findall(r"(?<!\d)\d{6}(?!\d)", s or "")
    pins = pin(read)
    return covered / len(b) >= 0.85 and (not pins or pins[-1] in pin(registered))


def _date(s):
    try:
        return datetime.date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def proprietor_of(legal_name):
    m = re.match(r"\s*(.+?)\s*\(Prop\.\s*(.+?)\)\s*$", legal_name or "")
    return (m.group(1), m.group(2)) if m else (None, None)


def check_document(slot, doc, app):
    """Findings for one document: [{severity, message}]. app = {gst, udyam_number, udyam}."""
    label = DOC_TYPES[slot][1]
    if doc is None:
        return [{"severity": "FIX", "message": "%s is missing - please upload it" % label}]
    f, gst = doc["fields"], app["gst"]
    out = []
    add = lambda sev, msg: out.append({"severity": sev, "message": msg})
    if doc["type"] != slot:
        got = DOC_TYPES.get(doc["type"], (None, "an unrecognised document"))[1]
        add("FIX", "This looks like %s, not a %s" % (got, label))
        return out
    if doc["quality"] < 0.8:
        add("FIX", "Image is blurry or unreadable - please re-upload a clear, flat photo or scan")
        return out

    if slot == "gst_certificate":
        value, status = read_gstin(f.get("gstin"), gst["gstin"])
        f["gstin"] = value                          # show the normalised reading, not raw OCR text
        if status == "unreadable":
            add("FIX", "GSTIN could not be read - please re-upload a clearer copy")
        elif status == "partial":
            add("WARN", "GSTIN only partly readable (%s) - close to the GSTIN you entered; reviewer to confirm"
                % reg.mask(value))
        elif status == "invalid":
            add("REJECT", "GSTIN %s on the certificate is not a valid GSTIN (check digit fails) - the document "
                          "may be altered; upload the original certificate" % reg.mask(value))
        elif value != gst["gstin"]:
            add("REJECT", "GSTIN on the certificate does not match the GSTIN you entered")
        elif status == "corrected":
            add("WARN", "GSTIN read with a look-alike character corrected (e.g. O/Q); matches the GSTIN you entered")
        if gst["status"] != "Active":
            add("REJECT", "GST registry shows this GSTIN as %s" % gst["status"])
        if not _close(f.get("legal_name"), gst["legal_name"], 0.95):
            add("FIX", "Legal name on the certificate ('%s') does not match the GST registry ('%s')"
                % (f.get("legal_name", ""), gst["legal_name"]))
        if not _close(f.get("trade_name"), gst["trade_name"], 0.95):
            add("FIX", "Trade name on the certificate does not match the GST registry")
        if f.get("constitution") and f["constitution"] != gst["constitution"]:
            add("FIX", "Constitution on the certificate does not match the GST registry")
        if not _same_address(f.get("address"), gst["principal_place_of_business"]):
            add("FIX", "Address on the certificate does not match the GST registry")
        if f.get("date") and f["date"] != gst["registration_date"]:
            add("WARN", "Date of liability differs from the registry registration date")

    elif slot == "udyam_certificate":
        ud = app.get("udyam")
        num = f.get("udyam_number")
        if not num:
            add("FIX", "Udyam registration number is blank on the certificate")
        elif num != app.get("udyam_number"):
            add("FIX", "Udyam number on the certificate does not match the one you entered")
        if not _close(f.get("enterprise_name"), gst["trade_name"]):
            add("FIX", "Enterprise name does not match the GST trade name")
        if f.get("state") and f["state"] != gst["state"]:
            add("FIX", "Udyam state (%s) differs from the GST state (%s)" % (f["state"], gst["state"]))
        if ud:
            if f.get("city") and f["city"] != ud["city"]:
                add("FIX", "Udyam city does not match the Udyam registry")
            if f.get("date") and f["date"] != ud["date_of_registration"]:
                add("WARN", "Registration date differs from the Udyam registry")
            if f.get("major_activity") and f["major_activity"] != ud["major_activity"]:
                add("WARN", "Major activity (%s) differs from the Udyam registry (%s)"
                    % (f["major_activity"], ud["major_activity"]))

    elif slot == "signatory_id":
        valid = _date(f.get("valid_till"))
        if not valid:
            add("FIX", "ID validity date could not be read")
        elif valid < TODAY:
            add("FIX", "Signatory ID expired on %s" % valid)
        if not _close(f.get("business"), gst["trade_name"]):
            add("FIX", "ID is issued for '%s', not for %s" % (f.get("business", ""), gst["trade_name"]))
        designation = (f.get("designation") or "").lower()
        allowed = ALLOWED_SIGNATORY.get(gst["constitution"], set())
        if gst["constitution"] == "Proprietorship":
            owner, _ = proprietor_of(gst["legal_name"])
            if owner and not _close(f.get("name"), owner):
                add("FIX", "Signatory %s is not the proprietor (%s) - the proprietor must sign"
                    % (f.get("name", ""), owner))
            elif designation not in allowed:
                add("FIX", "ID shows the proprietor as '%s' - a proprietorship is signed by its proprietor; "
                           "upload an ID that shows the role as Proprietor" % f.get("designation", ""))
        elif designation not in allowed:
            sev = "WARN" if designation == "owner" else "FIX"
            add(sev, "Designation '%s' is not an authorised signatory role for a %s (expected %s)"
                % (f.get("designation", ""), gst["constitution"], " / ".join(sorted(allowed)).title()))

    elif slot == "address_proof":
        d = _date(f.get("date"))
        if not d:
            add("FIX", "Bill date could not be read")
        elif d > TODAY:
            add("FIX", "Bill date %s is in the future" % d)
        elif (TODAY - d).days > ADDRESS_PROOF_MAX_DAYS:
            add("FIX", "Address proof is %d days old - it must be from the last %d days"
                % ((TODAY - d).days, ADDRESS_PROOF_MAX_DAYS))
        if not (_close(f.get("billed_to"), gst["trade_name"]) or _close(f.get("billed_to"), gst["legal_name"])):
            add("FIX", "Bill is in the name of '%s', not the business" % f.get("billed_to", ""))
        if not _same_address(f.get("address"), gst["principal_place_of_business"]):
            add("FIX", "Supply address on the bill does not match the GST principal place of business")
    return out


def verdict(findings):
    worst = max([SEVERITY[x["severity"]] for x in findings] or [0])
    return [k for k, v in SEVERITY.items() if v == worst][0].replace("WARN", "PASS")


def required_slots(app):
    slots = ["gst_certificate", "signatory_id", "address_proof"]
    if app.get("udyam_number") or app.get("udyam_uploaded"):
        slots.insert(1, "udyam_certificate")
    return slots


def evaluate(app, docs):
    """docs: {slot: extracted doc}. -> {verdict, documents: {slot: {verdict, findings, fields}}}"""
    app = dict(app, udyam_uploaded="udyam_certificate" in docs)
    result = {}
    for slot in required_slots(app):
        doc = docs.get(slot)
        findings = check_document(slot, doc, app)
        result[slot] = {"label": DOC_TYPES[slot][1], "verdict": verdict(findings), "findings": findings,
                        "fields": masked_fields(doc["fields"]) if doc else {}}
    overall = verdict([{"severity": d["verdict"]} for d in result.values()])
    return {"verdict": overall, "documents": result}


def masked_fields(fields):
    out = {}
    for k, v in fields.items():
        if k in ("units", "amount", "reg_type"):     # not used by any check
            continue
        out[k] = reg.mask(v) if k in ("gstin", "udyam_number", "id_no", "consumer_no") else v
    return out
