import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import server  # noqa: E402
from core import advisor, kyc, registry  # noqa: E402

server.store.DB = os.path.join(tempfile.mkdtemp(), "test.db")   # never touch the demo database
REG = registry.get()
P = REG.products


def prof(**kw):
    base = dict(segment="micro", city_tier=2, employees=3, sites=1, gstin_active=True, fibre_feasible=True, interests=[])
    base.update(kw)
    return base


class GstinTest(unittest.TestCase):
    def test_every_registry_gstin_passes_format_and_checksum(self):
        self.assertEqual([g for g in REG.gst if registry.gstin_format_errors(g)], [])

    def test_bad_checksum_and_shape(self):
        self.assertIn("check digit", registry.gstin_format_errors("32TTNXB7384T1ZX")[0])
        self.assertTrue(registry.gstin_format_errors("32TTNXB7384T1Z"))

    def test_lookup_rejects_cancelled_and_unknown(self):
        self.assertFalse(REG.lookup_gstin("37IHKXV5167L1ZS")["ok"])           # Cancelled
        self.assertTrue(REG.lookup_gstin("32ttnxb7384t1zw")["ok"])            # case-insensitive, Active

    def test_udyam_must_match_gst_business(self):
        gst = REG.gst["32TTNXB7384T1ZW"]
        self.assertTrue(REG.lookup_udyam("UDYAM-KL-00-3078801", gst)["ok"])
        self.assertFalse(REG.lookup_udyam("UDYAM-TN-00-3866196", gst)["ok"])

    def test_mask(self):
        self.assertEqual(registry.mask("27QTBXZ1995X1Z9"), "27QTB•••••••1Z9")
        self.assertEqual(registry.mask("UDYAM-MH-00-7656096"), "UDYAM-MH-00-•••6096")


class AdvisorTest(unittest.TestCase):
    def test_eligibility_rules(self):
        self.assertIn("tier", advisor.ineligible_reason(P["P03"], prof(city_tier=2, employees=10)))
        self.assertIn("GSTIN", advisor.ineligible_reason(P["P15"], prof(gstin_active=False)))
        self.assertIn("sites", advisor.ineligible_reason(P["P10"], prof(employees=20, sites=2)))
        self.assertIsNone(advisor.ineligible_reason(P["P01"], prof()))

    def test_dependency_is_resolved_not_violated(self):
        r = advisor.recommend(prof(interests=["P23"]), P)
        for t in r["tiers"]:
            items = [{"product_id": i["product_id"]} for i in t["items"]]
            self.assertEqual(advisor.bundle_violations(items, prof(interests=["P23"]), P), [], t["name"])

    def test_no_fibre_offers_airfiber(self):
        r = advisor.recommend(prof(fibre_feasible=False), P)
        self.assertTrue(all(t["items"][0]["product_id"] == "P04" for t in r["tiers"]))

    def test_no_gstin_lists_what_is_locked(self):
        r = advisor.recommend(prof(gstin_active=False, interests=["P15", "P14"]), P)
        self.assertEqual({x["product_id"] for x in r["ineligible"]}, {"P15", "P14"})

    def test_longer_contract_is_cheaper(self):
        items = [{"product_id": "P02", "qty": 1}]
        self.assertLess(advisor.price(items, 24, P)["monthly_total"], advisor.price(items, 12, P)["monthly_total"])


class KycTest(unittest.TestCase):
    EXPECTED = {"K01": "REJECT", "K02": "FIX", "K03": "PASS", "K04": "FIX", "K05": "FIX", "K06": "REJECT",
                "K07": "FIX", "K08": "FIX", "K09": "FIX", "K10": "PASS", "K11": "FIX", "K12": "PASS"}
    MUST_SAY = {"K01": "Cancelled", "K04": "blurry", "K05": "Udyam certificate is missing", "K06": "check digit",
                "K07": "Legal name", "K08": "Office admin", "K09": "Office admin", "K11": "257 days old"}

    @classmethod
    def setUpClass(cls):
        cls.results = {k: server.route("GET", "/api/kyc-lab/" + k, {}, {}) for k in cls.EXPECTED}

    def test_verdicts(self):
        self.assertEqual({k: r["verdict"] for k, r in self.results.items()}, self.EXPECTED)

    def test_planted_problem_is_named(self):
        for k, text in self.MUST_SAY.items():
            msgs = " ".join(f["message"] for d in self.results[k]["documents"].values() for f in d["findings"])
            self.assertIn(text, msgs, k)

    def test_ocr_lookalike_is_corrected_only_toward_entered_gstin(self):
        self.assertEqual(kyc.read_gstin("NO270HJXK0658U1ZL", "27QHJXK0658U1ZL"), ("27QHJXK0658U1ZL", "corrected"))
        self.assertEqual(kyc.read_gstin("NO08YKZXS8189L1Z0", "08YKZXS5189L1ZO")[1], "invalid")

    def test_stale_address_proof_rule(self):
        app = {"gst": REG.gst["32TTNXB7384T1ZW"]}
        doc = {"type": "address_proof", "quality": 1.0, "fields": {
            "date": "2026-04-16", "billed_to": "Balaji Dental Care LLP",
            "address": REG.gst["32TTNXB7384T1ZW"]["principal_place_of_business"]}}
        self.assertEqual(kyc.check_document("address_proof", doc, app), [])
        doc["fields"]["date"] = "2026-04-15"
        self.assertIn("91 days", kyc.check_document("address_proof", doc, app)[0]["message"])


class JourneyTest(unittest.TestCase):
    def test_happy_path_with_specimen_k03(self):
        import base64
        lead = server.route("GET", "/api/leads/L03571", {}, {})
        tier = server.route("POST", "/api/advise", {}, {"profile": lead["profile"]})["tiers"][1]
        app = server.route("POST", "/api/applications", {}, {
            "gstin": lead["gstin"], "udyam_number": lead["udyam_number"], "profile": lead["profile"],
            "items": tier["items"], "term": 12})
        self.assertNotIn(lead["gstin"], str(app))                       # identifiers masked in responses
        with self.assertRaises(server.ApiError):                         # no upload before consent
            server.route("POST", "/api/applications/%s/documents" % app["id"], {}, {"slot": "gst_certificate"})
        server.route("POST", "/api/applications/%s/consent" % app["id"], {}, {"accepted": True})
        for slot in kyc.DOC_TYPES:
            with open(os.path.join(server.SAMPLES, "K03_%s.png" % slot), "rb") as f:
                server.route("POST", "/api/applications/%s/documents" % app["id"], {},
                             {"slot": slot, "image_base64": base64.b64encode(f.read()).decode()})
        app = server.route("POST", "/api/applications/%s/submit" % app["id"], {}, {})
        self.assertEqual(app["kyc"]["verdict"], "PASS")
        self.assertEqual(app["stage"], "KYC_VERIFIED")
        self.assertEqual(server.store.load(app["id"])["docs"], {})      # extracted text dropped after decision

    def test_rule_breaking_bundle_is_refused(self):
        lead = server.route("GET", "/api/leads/L03571", {}, {})
        with self.assertRaises(server.ApiError):
            server.route("POST", "/api/applications", {}, {
                "gstin": lead["gstin"], "profile": lead["profile"], "items": [{"product_id": "P23", "qty": 1}]})

    def test_replay_finds_historic_rule_breaks(self):
        r = server.INSIGHTS["replay"]
        self.assertEqual(r["activated_with_inactive_gstin"], 22)
        self.assertEqual(r["bundle_rule_violations"], 58)   # 19 of them: product needs an ACTIVE GSTIN


if __name__ == "__main__":
    unittest.main()
