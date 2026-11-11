"""Firm Verifier API: one passing and one failing case per field type (verifier unit-test style), on synthetic cards."""

from __future__ import annotations

import json

import pytest

from vharvey.fv import api, common, docs, matters

E = [{"path": "9999-00001/a.docx", "quote": "evidence quote text here"}]
CARD = {
    "matter_id": "9999-00001", "client": {"name": "Acme Corp", "aliases": ["Acme"], "evidence": E},
    "description": "Acme v. Beta", "matter_type": {"value": "commercial_litigation", "evidence": E},
    "practice_areas": [{"value": "commercial_litigation", "evidence": E}, {"value": "capital_markets", "evidence": E}],
    "client_role": [{"value": "counterclaim_plaintiff", "evidence": E}], "counterparties": ["Beta"],
    "opened_date": {"value": "2022-03-01", "evidence": E},
    "status": {"value": "dormant", "date": "2023-06-01", "evidence": E},
    "closed_date": None,
    "outcome": {"value": "settled", "date": "2023-05-01", "detail": "settled then stipulated dismissal", "evidence": E},
    "relief_sought_by_client": [{"type": "compensatory_damages", "amount": "$1M", "evidence": E}],
    "terms_executed": [{"key": "contingent_value_right",
                        "evidence": [{"value": "$5M CVR", **E[0], "stage": "executed"}]}],
    "terms_draft_only": [{"key": "management_fee_offset", "evidence": [{"value": "100%", **E[0], "stage": "draft"}]}],
    "issues": [{"key": "anti_kickback", "depth": "mentioned", "evidence": E},
               {"key": "stark_law", "depth": "analysed", "evidence": E}],
    "people": {}, "documents": [],
}
VOCAB = {"practice_areas": [{"value": "commercial_litigation", "label": "Litigation", "synonyms": ["litigation"]},
                            {"value": "capital_markets", "label": "Capital Markets", "synonyms": []},
                            {"value": "tax", "label": "Tax", "synonyms": []}],
         "terms": [{"key": "earnout", "label": "Earnout", "synonyms": ["earn_out"]},
                   {"key": "contingent_value_right", "label": "CVR", "synonyms": ["cvr"]},
                   {"key": "management_fee_offset", "label": "", "synonyms": ["fee_offset"]}],
         "issues": [{"key": "anti_kickback", "label": "", "synonyms": ["aks"]},
                    {"key": "stark_law", "label": "", "synonyms": ["stark"]}]}


@pytest.fixture(autouse=True)
def fake_kb(tmp_path, monkeypatch):
    fv = tmp_path / "fv"
    (fv / "matters").mkdir(parents=True)
    (fv / "docs" / "9999-00001").mkdir(parents=True)
    (fv / "matters" / "9999-00001.json").write_text(json.dumps(CARD))
    (fv / "vocab.json").write_text(json.dumps(VOCAB))
    (fv / "docs" / "9999-00001" / "a.docx.json").write_text(json.dumps(
        {"doc_type": "lpa", "title": "LPA", "date": None, "stage": "draft", "stage_quote": "DRAFT", "signed": False,
         "summary": "s", "terms": [], "issues": [], "outcome_statements": [], "_meta": {"truncated": False}}))
    for mod in (api, common):
        monkeypatch.setattr(mod, "FV", fv)
    monkeypatch.setattr(api, "MATTERS", fv / "matters")
    monkeypatch.setattr(api, "DOCS", fv / "docs")
    monkeypatch.setattr(matters, "MATTERS", fv / "matters")
    monkeypatch.setattr(docs, "DOCS", fv / "docs")
    for f in (api.card, api.vocab, api._maps):
        f.cache_clear()
    yield
    for f in (api.card, api.vocab, api._maps):
        f.cache_clear()


def v(*a):
    return api.check("9999-00001", *a)["verdict"]


@pytest.mark.parametrize("args,expected", [
    (("practice_area", "litigation"), "TRUE"), (("practice_area", "tax"), "FALSE"),
    (("client_role", "plaintiff"), "TRUE"), (("client_role", "defendant"), "FALSE"),
    (("status", "dormant"), "TRUE"), (("status", "closed"), "FALSE"),
    (("outcome", "settled"), "TRUE"), (("outcome", "dismissed"), "FALSE"),
    (("closed_year", "2023"), "UNKNOWN"), (("opened_year", "2022"), "TRUE"), (("opened_year", "2021"), "FALSE"),
    (("relief_sought_by_client", "compensatory_damages"), "TRUE"), (("relief", "declaratory"), "FALSE"),
    (("term.cvr", "present"), "TRUE"), (("term.earnout", "present"), "NOT_FOUND"),
    (("deal_term.fee_offset", "present"), "FALSE"), (("earnout", None), "NOT_FOUND"),
    (("issue.stark", "analysed"), "TRUE"), (("issue.aks", "analysed"), "FALSE"), (("issue.aks", "mentioned"), "TRUE"),
    (("term.working_capital_adjustment", None), "UNKNOWN"),
    (("term.cvr_provision", None), "TRUE"),  # generic word dropped: still the executed CVR
    (("term.management_fee", None), "FALSE"),  # general key matches the specific draft-only offset term
    (("issue.hsr_second_request", "analysed"), "UNKNOWN"),  # not in the vocabulary: never NOT_FOUND
    (("term.earn_out_provision", "present"), "NOT_FOUND"), (("issue.kickback", "mentioned"), "TRUE"),
    (("term.anti_kickback", None), "TRUE"),  # agent picked the wrong prefix: still found as an issue
    (("practice_area", "Capital Markets"), "SECONDARY"), (("practice_area", "space law"), "UNKNOWN"),
    (("outcome", "won big"), "UNKNOWN"), (("client_role", "astronaut"), "UNKNOWN"),
])
def test_check(args, expected):
    assert v(*args) == expected


def test_evidence_and_unknowns():
    r = api.check("9999-00001", "outcome", "dismissed")
    assert r["evidence"] == E and r["actual"]["value"] == "settled"
    assert api.check("0000-00000", "outcome", "settled")["verdict"] == "UNKNOWN"
    bad = api.check("9999-00001", "colour", "red")
    assert bad["verdict"] == "UNKNOWN" and "error" in bad


def test_matter_and_doc():
    m = api.matter("9999-00001")
    assert m["terms_executed"] == ["contingent_value_right"] and m["issues_mentioned_only"] == ["anti_kickback"]
    d = api.doc("documents/matters/9999-00001/a.docx")
    assert d["stage"] == "draft" and "error" not in d
    assert "error" in api.doc("9999-00001/missing.docx")


def test_grounding():
    common.norm_text.cache_clear()
    text = 'This **AGREEMENT** (the \\"Agreement\\") is dated as of\nMay 1, 2023 between Acme and Beta.'
    import vharvey.k0 as k0
    orig = k0.text
    k0.text = lambda p: text
    try:
        assert common.grounded("x", 'This AGREEMENT (the "Agreement") is dated as of May 1, 2023')
        assert common.grounded("x", "This AGREEMENT ... between Acme and Beta")
        assert not common.grounded("x", "dated as of June 1, 2023 between")
        assert not common.grounded("x", "short")
    finally:
        k0.text = orig
        common.norm_text.cache_clear()


def test_check_complete():
    full = api.check_complete([{"field": "outcome", "value": "settled"}], ["9999-00001"])
    assert full["verdict"] == "TRUE" and full["n_index_matches"] == 1 and not full["missing_from_your_list"]
    miss = api.check_complete([{"field": "outcome", "value": "settled"}], [])
    assert miss["verdict"] == "FALSE" and miss["missing_from_your_list"][0]["matter_id"] == "9999-00001"
    contra = api.check_complete([{"field": "outcome", "value": "dismissed"}], ["9999-00001"])
    assert contra["listed_but_contradicted"][0]["matter_id"] == "9999-00001"
    assert "error" in api.check_complete([{"field": "colour", "value": "red"}], [])


def test_closed_year_v3():
    base = json.loads(json.dumps(CARD))
    cases = {
        "deal_closed": ({"status": None, "closed_date": None,
                         "outcome": {"value": "transaction_closed", "date": "2023-05-19", "evidence": E}}, "TRUE"),
        "dormant_settled": ({"status": {"value": "dormant", "date": "2023-06-01", "evidence": E}, "closed_date": None,
                             "outcome": {"value": "settled", "date": "2023-03-10", "evidence": E}}, "UNKNOWN"),
        "closed_status": ({"status": {"value": "closed", "date": "2022-12-01", "evidence": E}, "closed_date": None,
                           "outcome": {"value": "ongoing", "date": None, "evidence": E}}, "FALSE"),
    }
    for name, (patch, want) in cases.items():
        (api.MATTERS / "9999-00001.json").write_text(json.dumps({**base, **patch}))
        api.card.cache_clear()
        assert api.check("9999-00001", "closed_year", "2023")["verdict"] == want, name


def test_complete_leads_carry_evidence():
    r = api.check_complete([{"field": "outcome", "value": "settled"}], [])
    lead = r["missing_from_your_list"][0]
    assert lead["evidence"] and lead["evidence"][0]["path"] == E[0]["path"]
    assert "warning" not in r

