# Privacy note — Udyam Digital onboarding

We treat every business and person in this flow as real customer data, even though the hackathon data is fictional.

**1. We collect only what each step needs.**

| Step | What we collect | Why |
|---|---|---|
| Business | GSTIN; Udyam number (optional) | We fetch name, constitution and address from the registry, so the customer doesn't type them |
| Needs | Business type, city tier, employee count, number of sites, fibre availability | To decide which products are eligible |
| Quote | Chosen products and quantities | To price the quote and plan installation |
| KYC | GST certificate, Udyam certificate (only if a Udyam number was given), signatory ID, an address proof from the last 90 days | To verify the business and its authorised signatory |

We do not ask for Aadhaar numbers, bank statements or photos beyond these documents.

**2. Consent comes before KYC.** A plain-language notice says why we need the documents, how they are checked and how long anything is kept. The server refuses uploads until consent is recorded; the record holds the notice version and the date.

**3. We store as little as possible.**
- Document images are processed in memory and in a temporary file that exists only while OCR runs. They are **never stored**.
- Only the extracted fields and the verification result are kept.
- When KYC passes, the extracted document text is deleted. Only the verdict and the masked fields remain.

**4. Identifiers are masked everywhere.**
- GSTIN, Udyam, ID and consumer numbers are masked in the UI, API responses, server logs and the audit log, e.g. `27QTB•••••••1Z9`, `UDYAM-MH-00-•••6096`.
- The server log rewrites any identifier that appears in a URL.

**5. Retention**

| Data | How long it is kept |
|---|---|
| Document images | Not stored |
| Extracted document fields | Until KYC passes, or 30 days after an application is abandoned |
| Masked KYC result and audit trail | Contract term + 1 year, or longer if the law requires (e.g. telecom subscriber-verification rules) |
| Quote and profile | Contract term + 1 year |

**6. Access and audit.** Every action on an application is written to an append-only audit log: created, consent given, each upload and its verdict, submission. The log holds no raw identifiers. Staff see the same masked view as the customer; unmasked access would be role-based and logged.

**7. Customer rights.** A customer can ask what we hold, correct it (by re-uploading a document), or withdraw before activation. Withdrawing deletes everything except the masked audit trail.

**8. Where data lives.** The prototype runs on a single machine and listens only on localhost (`127.0.0.1`). No third-party OCR or cloud service sees the documents: OCR runs on the device.
