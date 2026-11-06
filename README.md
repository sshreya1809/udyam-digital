# Udyam Digital

A small business goes from **GSTIN → needs discovery → 3-tier quote → Smart KYC documents → live activation tracking** online in one session, with no sales visit. A salesperson or channel partner can also run the exact same flow on the customer's behalf.

---

## Quick Start (Zero-Setup Instant Run)

The repository includes the pre-built React application (`frontend/dist`) and pre-cached OCR extractions for all 47 test applicant documents (`data/ocr_cache`). The backend uses only the **Python standard library** — no `pip install` or external database configuration is needed!

### Run on Windows

1. **Start the backend server:**
   ```powershell
   python server.py
   ```
2. **Open the web application:**
   Navigate to **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

3. **Run the automated unit tests:**
   ```powershell
   python -m unittest discover -s tests
   ```
   *(All 17 tests will run and pass in ~0.25 seconds).*

---

### Run on macOS

```sh
# Optional: re-compile OCR binary and rebuild React
./setup.sh            

# Start the server (http://127.0.0.1:8000)
python3 server.py     

# Run unit tests
python3 -m unittest discover -s tests
```

---

## Frontend Development (Optional: Hot-Reload)

The frontend is built with **React 19 + Vite** in `frontend/`. If you want to modify the frontend with instant hot-reload:

1. In Terminal 1, keep the backend running:
   ```sh
   python server.py
   ```
2. In Terminal 2, launch the Vite dev server:
   ```sh
   cd frontend
   npm install
   npm run dev
   ```
3. Open **[http://127.0.0.1:5173](http://127.0.0.1:5173)** (Vite automatically proxies `/api` calls to the Python server on port 8000).

---

## How to Demo the Prototype

1. **Step 1 — Business Lookup:** Pick one of the sample test leads (`K01`–`K12`) from the dropdown, or enter a custom GSTIN to see the instant live validation against `mock_gstin_registry.csv`.
2. **Step 2 — Needs Discovery:** Select the business archetype (Kirana, Clinic, Multi-site, Workshop), employee count, sites, and fiber availability.
3. **Step 3 — 3-Tier Quote:** Review the **Essential**, **Recommended**, or **Complete** bundles with transparent monthly pricing and toggleable add-ons with automatic dependency enforcement.
4. **Step 4 — Smart KYC:** View the DPDP Act 2023 consent screen, then pick the matching specimen document pack for your applicant (`K01`–`K12`) to watch the validation engine detect planted defects in real time.
5. **Step 5 — Live Order Tracker:** Track the simulated milestone activation journey and dynamic installation dates derived from catalogue lead times.
6. **Tabs:**
   - **KYC Lab Tab:** A dedicated test bench to run and inspect all 12 specimen applicant document sets side-by-side.
   - **Insights Tab:** In-depth funnel drop analysis and replay of past sales showing rule violations and NPS impact.

---

## Why this design: what the data says

| Funnel stage (`smb_leads.csv`, 5,000 leads) | Lost | Main reasons | Module |
|---|---|---|---|
| Contacted → Needs assessed | 1,432 | no time for a visit (531), visit not scheduled (296) | **Self-serve advisor:** no visit |
| Needs assessed → Quote | 1,113 | price (414), competitor cheaper (207), too complex (206), too slow (179) | **Instant 3-option quote** |
| Quote → KYC | 273 | missing GST/Udyam (94), paperwork too long (79), signatory absent (53), mismatch (47) | **Registry lookup + Smart KYC** |
| KYC → Activated | 220 | install >21 days (98), fibre not feasible (41) | **Tracker + feasibility check before the quote** |

### Additional Data Findings:
- **Past sales broke the rules.** Replaying historical sales through the rules engine finds **22 activations on a Cancelled or Suspended GSTIN** and **58 sold bundle lines that break catalogue rules** (wrong tier, needs active GSTIN, missing dependency, insufficient employees). Rules are enforced on the server, not left to the salesperson.
- **Chasing lowers NPS.** It falls from 7.5 for customers who chased status once to 6.0 for those who chased 5 or more times. The tracker pushes proactive WhatsApp updates so customers never have to call.
- **Names are ambiguous.** 212 GST names and 648 Udyam names are duplicated in the registries; every lookup is therefore indexed strictly by ID, never by name.

---

## Architecture & Modules

| File | What it does |
|---|---|
| `core/registry.py` | GSTIN format and mod-36 checksum (accepts `X`), state code, registry lookup (must be **Active**), Udyam lookup cross-checked against GST state and name, identifier masking |
| `core/advisor.py` | Eligibility from the catalogue (`city tier`, `min_employees`, `min_sites`, `requires_gstin`, fibre feasibility); `requires_one_of` dependencies resolved by auto-adding the cheapest eligible base; 3 tiers; price within the catalogue range (24-month contract = minimum price, 12-month = midpoint) |
| `core/kyc.py` | OCR → fields (watermark-tolerant, corrects for tilted scans) → checks against the registry and rules → per-document `PASS / FIX / REJECT` with a fix-it message |
| `core/tracker.py` | Expected dates from `typical_install_days` (slowest product in the bundle), stage timeline, customer messages, escalation after 21 days |
| `core/insights.py` | Funnel and drop-reason analysis, replay of past sales through the rules engine |
| `server.py` | Zero-dependency JSON API and static file server; the DPDP consent gate comes before any upload; application writes are serialized |
| `frontend/src/` | React UI: `steps/` (Business, Needs, Quote, KYC, Track), `KycLab.jsx`, `Insights.jsx` |

---

## Smart KYC Rules & Planted Defect Traps

| Rule | Caught in | Verdict |
|---|---|---|
| GSTIN is not Active in the registry | K01 | REJECT (Cancelled) |
| Required field is blank | K01 | FIX (Missing Udyam number) |
| Image is blurry or unreadable | K04 | FIX (Re-upload requested) |
| Expected document is missing | K05 | FIX (Missing Udyam certificate) |
| GSTIN is well-formed but fails check digit | K06 | REJECT (Altered or mistyped) |
| Legal name differs from registry | K07 | REJECT ("Shri" vs "Neelgiri") |
| Signatory role doesn't fit constitution | K01, K02, K07, K08, K09 | WARN (Where ID says "Owner") |
| Address proof > 90 days old (today = 2026-07-15) | K11 | REJECT (Bill is 257 days old) |
| Bill name/address doesn't match business | Tested on cross-upload | REJECT |

The clean packs **K03, K10, and K12 pass cleanly**. `tests/test_prototype.py` locks in all 12 verdicts.

---

## Privacy & DPDP Act 2023 Compliance

- **Consent First**: In-app plain-language consent notice displayed and recorded before any document upload.
- **Data Minimisation**: No permanent storage of document images; OCR is run ephemerally in-memory and wiped.
- **PII Masking**: Identifiers masked in UI, logs, and APIs (`27QTB•••••••1Z9`, `UDYAM-MH-00-•••6096`).
- Full details in `PRIVACY.md`.
