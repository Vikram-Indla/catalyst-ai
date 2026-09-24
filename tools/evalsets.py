"""`python -m tools.evalsets search`: write the synthetic retrieval corpus and its labelled set."""

import hashlib
import json
import sys
from pathlib import Path

from tools import rules
from tools.corpus_terms import DOMAINS, INJECTIONS, PARAPHRASES, ROLES
from tools.evalsets_assistant import write_assistant
from tools.evalsets_brief import write_brief
from tools.evalsets_documents import write_documents
from tools.evalsets_drafts import write_drafts
from tools.evalsets_hubs import write_hub
from tools.evalsets_query import write_query
from tools.evalsets_strata import write_strata
from tools.evalsets_threads import write_threads
from tools.evalsets_workflow import write_workflow

ORG_A = "11111111-1111-7111-8111-111111111111"
ORG_B = "22222222-2222-7222-8222-222222222222"
VERSION = "1.0.0"
CORPUS = "work_items"


def _hash(title: str | None, text: str) -> str:
    return hashlib.sha256(f"{title}\n{text}".encode()).hexdigest()


def _story(domain: str, name: str, feature: tuple[str, str, str], n: int) -> dict[str, object]:
    phrase, alias, term = feature
    role = ROLES[n % len(ROLES)]
    title = f"{phrase.capitalize()}"
    text = (
        f"As a {role}, I want {phrase} so that the {name.lower()} work is easier to finish.\n\n"
        f"Also known as {alias}. The {term} setting lives under {name}. Acceptance: given a "
        f"member on the {name.lower()} screen, when they use {phrase}, then the result is "
        f"saved and shown. Related key PRJ-{n:03d}."
    )
    return {"kind": "story", "title": title, "text": text, "domain": domain}


def _bug(domain: str, name: str, feature: tuple[str, str, str], n: int) -> dict[str, object]:
    phrase, alias, term = feature
    title = f"{phrase.capitalize()} fails"
    text = (
        f"{phrase.capitalize()} fails when the {term} value is empty.\n\n"
        f"Steps: open {name}, start {alias}, submit. Expected: the {term} is accepted. "
        f"Actual: an error appears and nothing is saved. Seen on build {n + 4_100}."
    )
    return {"kind": "bug", "title": title, "text": text, "domain": domain}


def corpus_lines() -> list[dict[str, object]]:
    """Return every corpus line: 100 items of one organisation, 4 poison, 10 copies elsewhere."""
    lines: list[dict[str, object]] = []
    n = 0
    for domain, name, features in DOMAINS:
        for index, feature in enumerate(features):
            for build in (_story, _bug):
                n += 1
                item = build(domain, name, feature, n)
                lines.append(
                    {
                        "organization_id": ORG_A,
                        "external_id": f"{domain.upper()}-{index}-{item['kind']}",
                        "kind": item["kind"],
                        "title": item["title"],
                        "text": item["text"],
                        "data_class": "CONFIDENTIAL",
                        "feature": f"{domain}-{index}",
                    }
                )
    for i, injection in enumerate(INJECTIONS):
        lines.append(
            {
                "organization_id": ORG_A,
                "external_id": f"POISON-{i}",
                "kind": "story",
                "title": "Note",
                "text": injection,
                "data_class": "CONFIDENTIAL",
                "feature": "poison",
            }
        )
    for line in lines[:10]:
        copy = dict(line)
        copy["organization_id"] = ORG_B
        copy["external_id"] = "B-" + str(line["external_id"])
        lines.append(copy)
    return lines


def _request(mode: str, text: str, **extra: object) -> dict[str, object]:
    request: dict[str, object] = {
        "organization_id": ORG_A,
        "capability_version": VERSION,
        "corpus": CORPUS,
        "mode": mode,
        "text": text,
    }
    request.update(extra)
    return request


def _case(
    case_id: str, request: dict[str, object], tags: list[str], expected: dict[str, object]
) -> dict[str, object]:
    return {"id": case_id, "input": request, "tags": tags, "expected": expected}


Features = dict[str, list[dict[str, object]]]


def _similar_cases(by_feature: Features) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for feature, pair in by_feature.items():
        story, bug = pair
        for item, other in ((story, bug), (bug, story)):
            if item["kind"] == "bug" and int(feature.split("-")[1]) % 2:
                continue
            text = f"{item['title']}\n\n{item['text']}"
            request = _request("similar", text, exclude_external_ids=[item["external_id"]])
            cases.append(
                _case(
                    f"similar-{item['external_id']}",
                    request,
                    ["similar", f"domain:{feature.split('-')[0]}"],
                    {"relevant": [other["external_id"]]},
                )
            )
    return cases


def _query_cases(by_feature: Features) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for domain, _, features in DOMAINS:
        for index, (phrase, alias, _) in enumerate(features):
            if index % 5 == 4:
                continue
            ids = [str(line["external_id"]) for line in by_feature[f"{domain}-{index}"]]
            query = phrase if index % 2 == 0 else alias
            cases.append(
                _case(
                    f"query-{domain}-{index}",
                    _request("query", query, k=10),
                    ["query", f"domain:{domain}"],
                    {"relevant": ids},
                )
            )
    for domain, index, paraphrase in PARAPHRASES:
        ids = [str(line["external_id"]) for line in by_feature[f"{domain}-{index}"]]
        cases.append(
            _case(
                f"paraphrase-{domain}-{index}",
                _request("query", paraphrase),
                ["query", "paraphrase", f"domain:{domain}"],
                {"relevant": ids},
            )
        )
    return cases


def _injection_cases(by_feature: Features, copies: list[str]) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for i, injection in enumerate(INJECTIONS):
        feature = list(by_feature)[i * 7 % len(by_feature)]
        phrase = str(by_feature[feature][0]["title"]).lower()
        cases.append(
            _case(
                f"injection-{i}",
                _request("query", f"{phrase} {injection}"),
                ["query", "injection"],
                {"inert": True, "forbidden": copies},
            )
        )
        cases.append(
            _case(
                f"injection-similar-{i}",
                _request("similar", f"{injection}\n\n{phrase}"),
                ["similar", "injection"],
                {"inert": True, "forbidden": copies},
            )
        )
    return cases


def _tenancy_and_filter_cases(
    lines: list[dict[str, object]], by_feature: Features, copies: list[str]
) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for line in lines[:6]:
        text = f"{line['title']}\n\n{line['text']}"
        relevant = [
            str(x["external_id"])
            for x in by_feature[str(line["feature"])]
            if x["external_id"] != line["external_id"]
        ]
        cases.append(
            _case(
                f"tenancy-{line['external_id']}",
                _request("similar", text, exclude_external_ids=[line["external_id"]]),
                ["similar", "tenancy"],
                {"relevant": relevant, "forbidden": copies},
            )
        )
    for kind in ("bug", "story"):
        for domain, index in (("export", 0), ("auth", 1)):
            ids = [
                str(line["external_id"])
                for line in by_feature[f"{domain}-{index}"]
                if line["kind"] == kind
            ]
            phrase = DOMAINS[[d[0] for d in DOMAINS].index(domain)][2][index][0]
            cases.append(
                _case(
                    f"filter-{kind}-{domain}-{index}",
                    _request("query", phrase, kinds=[kind]),
                    ["query", "filter"],
                    {"relevant": ids, "only_kinds": [kind]},
                )
            )
    return cases


def set_lines(lines: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return the labelled cases: similar per item, queries per feature, injection, tenancy."""
    by_feature: Features = {}
    for line in lines:
        if line["organization_id"] == ORG_A and line["feature"] != "poison":
            by_feature.setdefault(str(line["feature"]), []).append(line)
    copies = [str(line["external_id"]) for line in lines if line["organization_id"] == ORG_B]
    return (
        _similar_cases(by_feature)
        + _query_cases(by_feature)
        + _injection_cases(by_feature, copies)
        + _tenancy_and_filter_cases(lines, by_feature, copies)
    )


def write(name: str) -> int:
    """Write `corpus.jsonl` and `set.jsonl` for the named set."""
    directory = Path(rules.EVALS) / name
    lines = corpus_lines()
    for line in lines:
        line["content_hash"] = _hash(
            str(line["title"]) if line["title"] is not None else None, str(line["text"])
        )
    cases = set_lines(lines)
    (directory / "corpus.jsonl").write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines), encoding="utf-8"
    )
    (directory / "set.jsonl").write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8"
    )
    print(f"wrote {len(lines)} corpus lines and {len(cases)} cases for {name}")
    return 0


def main(name: str) -> int:
    """Write the named set: the retrieval corpus and cases, or a thread set."""
    writers = {
        "summarize": write_threads,
        "translate": write_threads,
        "propose-workflow": write_workflow,
        "release-notes": write_hub,
        "generate-tests": write_hub,
        "post-mortem": write_hub,
        "documents": write_documents,
        "documents-generate": write_documents,
        "documents-ingest": write_documents,
        "assistant": write_assistant,
        "unfurl": write_assistant,
        "interpret-query": write_query,
        "brief": write_brief,
        "improve-story": write_strata,
        "generate-children": write_strata,
        "translate-drafts": write_drafts,
    }
    return writers.get(name, write)(name)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "search"))
