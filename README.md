# Udyam Digital — prototype (Accel YTL Hackathon, Track A)

A small business goes from **GSTIN → needs → quote → documents → live tracking** online in one session, with no sales visit. A salesperson can also run the same flow on the customer's behalf.

## Run (macOS)

```sh
./setup.sh            # once: compiles the OCR helper (macOS Vision, ~2 min) and builds the React app
python3 server.py     # http://127.0.0.1:8000  (serves the API and the React build)
python3 -m unittest discover -s tests
```

- **Frontend:** React 19 + Vite in `frontend/`. For hot reload during development:
  1. Run `python3 server.py`.
  2. Then `cd frontend && npm run dev` and open http://127.0.0.1:5173 (it proxies `/api` to the Python server).
- **Backend:** standard-library Python 3.9 (`server.py`, `core/`), listening on `127.0.0.1` only.
- **Node.js:** a project-local copy lives in `.tools/node`; `setup.sh` puts it on `PATH`. `frontend/.npmrc` pins the public npm registry for this project only.
- **To demo:** pick a sample lead (K01–K12) on step 1. On step 4, pick the matching specimen pack.

## Why this design: what the data says

| Funnel stage (`smb_leads.csv`, 5,000 leads) | Lost | Main reasons | Module |
|---|---|---|---|
| Contacted → Needs assessed | 1,432 | no time for a visit (531), visit not scheduled (296) | **Self-serve advisor:** no visit |
| Needs assessed → Quote | 1,113 | price (414), competitor cheaper (207), too complex (206), too slow (179) | **Instant 3-option quote** |
| Quote → KYC | 273 | missing GST/Udyam (94), paperwork too long (79), signatory absent (53), mismatch (47) | **Registry lookup + Smart KYC** |
| KYC → Activated | 220 | install >21 days (98), fibre not feasible (41) | **Tracker + feasibility check before the quote** |

Other findings:
- **Past sales broke the rules.** Replaying them through the rules engine finds **22 activations on a Cancelled or Suspended GSTIN** and **58 sold bundle lines that break catalogue rules** (wrong tier, needs an active GSTIN, missing dependency, too few employees). Rules are enforced on the server, not left to the salesperson.
- **Chasing lowers NPS.** It falls from 7.5 for customers who chased status once to 6.0 for those who chased 5 or more times. So the tracker pushes WhatsApp updates; the customer should never have to call.
- **Names are ambiguous.** 212 GST names and 648 Udyam names are duplicated, so every lookup is by ID, never by name.

## Modules

| File | What it does |
|---|---|
| `core/registry.py` | GSTIN format and mod-36 checksum (accepts `X`), state code, registry lookup (must be **Active**), Udyam lookup cross-checked against GST state and name, identifier masking |
| `core/advisor.py` | Eligibility from the catalogue (`city tier`, `min_employees`, `min_sites`, `requires_gstin`, fibre feasibility); `requires_one_of` dependencies resolved by auto-adding the cheapest eligible base; 3 tiers; price within the catalogue range (24-month contract = minimum price, 12-month = midpoint) |
| `core/kyc.py` | OCR → fields (watermark-tolerant, corrects for tilted scans) → checks against the registry and rules → per-document `PASS / FIX / REJECT` with a fix-it message |
| `core/tracker.py` | Expected dates from `typical_install_days` (slowest product in the bundle), stage timeline, customer messages, escalation after 21 days |
| `core/insights.py` | Funnel and drop-reason analysis, replay of past sales through the rules engine |
| `server.py` | JSON API, serves the React build; the consent gate comes before any upload; application writes are serialised |
| `frontend/src/` | React UI: `steps/` (Business, Needs, Quote, KYC, Track), `KycLab.jsx`, `Insights.jsx` |

### Smart KYC rules, and what they catch in the specimen pack

| Rule | Caught in |
|---|---|
| GSTIN is not Active in the registry | K01 (Cancelled) |
| Required field is blank | K01 (Udyam number) |
| Image is blurry or unreadable → re-upload | K04 |
| Expected document is missing | K05 (Udyam certificate) |
| GSTIN is well-formed but fails the check digit → **reject** (altered or mistyped) | K06 |
| Legal name differs from the registry | K07 ("Shri" vs "Neelgiri") |
| Signatory role doesn't fit the constitution (proprietorship → proprietor; LLP → designated partner; Pvt Ltd → director) | K01, K02, K07, K08, K09 (warning only where the ID says "Owner") |
| Address proof is more than 90 days old (today = 2026-07-15) | K11 (257 days) |
| Bill name or address doesn't match the business | tested by uploading another business's bill |

The clean packs **K03, K10 and K12 pass**. `tests/test_prototype.py` locks in all 12 verdicts.

How OCR mistakes are handled without letting fraud through:
- Characters are corrected by position: GSTIN positions 1–2 are digits, 3–7 letters, and so on.
- A single look-alike swap (O↔Q, 6↔G) is accepted **only if** the result exactly equals the GSTIN the applicant entered and passes the checksum.
- A malformed read is treated as an OCR failure: it becomes a warning for a reviewer, or a re-upload request.
- A well-formed number with a wrong check digit is rejected.

Udyam registration dates, and activity on some certificates, differ from the registry across almost all specimens. These show as warnings, not blocks.

## Prototype limits

- OCR uses the macOS Vision framework. On another OS, swap `ocr/ocr` for Tesseract; the extraction logic doesn't change.
- Fibre feasibility is self-declared; it would come from a coverage map.
- Payments, real messaging and the sales console are simulated.
- Onboarding a business without a GSTIN online is out of scope. The advisor shows which products such businesses can buy and which a GSTIN would unlock.
- The in-app consent text and retention policy are in `PRIVACY.md`.
