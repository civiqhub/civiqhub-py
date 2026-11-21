# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Extract from the OpenAPI contract of the API the routes and fields that ApiSource reads.

The contract of the API is not public. This script keeps only what the code of the SDK
names anyway: the routes of the articles that ``ApiSource`` calls, their query
parameters, and the fields it reads in the answers, with their types. It keeps no
description and no other route. The fake API of the tests serves its answers from the
extract, so that a route or a field outside the contract fails a test.

Run it from the root of the repository, on the frozen contract of the API::

    python tests/contract/extract.py path/to/openapi-candidate.json

It writes ``tests/contract/articles.json``. A route or a field that the contract no longer
has stops the script.
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

#: The routes that ApiSource calls, by operationId of the contract.
ROUTES = ("listProjectArticles", "listArticleVersions", "getArticleVersion")

#: The fields that ApiSource reads, by schema of the contract.
FIELDS = {
    "ArticleListItemDto": ("id",),
    "ArticleVersionListItemDto": ("versionNumber", "publishedAt"),
    "ArticleVersionResponseDto": (
        "title",
        "description",
        "body",
        "publishedAt",
        "outline",
        "proposalBlocks",
    ),
    "ArticleOutlineEntryDto": ("paragraphId", "level", "number", "title"),
    "ArticleBodyProposalBlockDto": ("proposalId", "role", "paragraphId"),
    "OffsetPaginationMeta": ("hasNextPage",),
}

TARGET = Path(__file__).with_name("articles.json")


def _schema_name(node: dict[str, Any]) -> str | None:
    if "$ref" in node:
        return str(node["$ref"]).rsplit("/", 1)[1]
    for key in ("allOf", "oneOf", "anyOf"):
        if key in node and len(node[key]) == 1:
            return _schema_name(node[key][0])
    return None


def _field(node: dict[str, Any]) -> dict[str, Any]:
    """Keep the type of a field: its kind, whether it may be null, its choices."""
    kept: dict[str, Any] = {}
    name = _schema_name(node)
    if name is not None:
        kept["schema"] = name
    elif node.get("type") == "array":
        kept["type"] = "array"
        kept["items"] = _field(node["items"])
    else:
        kept["type"] = node["type"]
    for key in ("format", "enum", "minimum", "maximum"):
        if key in node:
            kept[key] = node[key]
    if node.get("nullable"):
        kept["nullable"] = True
    return kept


def _envelope(node: dict[str, Any]) -> dict[str, Any]:
    """Keep the answer of a route: a schema, or an object of pages ``{items, meta}``."""
    name = _schema_name(node)
    if name is not None:
        return {"schema": name}
    return {
        "type": "object",
        "required": sorted(node["required"]),
        "properties": {key: _field(value) for key, value in node["properties"].items()},
    }


def extract(contract: dict[str, Any]) -> dict[str, Any]:
    routes: dict[str, Any] = {}
    for path, operations in contract["paths"].items():
        for method, operation in operations.items():
            if not isinstance(operation, dict) or operation.get("operationId") not in ROUTES:
                continue
            answer = operation["responses"]["200"]["content"]["application/json"]["schema"]
            routes[operation["operationId"]] = {
                "method": method,
                "path": path,
                "path_parameters": sorted(
                    p["name"] for p in operation.get("parameters", []) if p["in"] == "path"
                ),
                "query_parameters": {
                    p["name"]: _field(p["schema"])
                    for p in operation.get("parameters", [])
                    if p["in"] == "query"
                },
                "answer": _envelope(answer),
            }
    missing = [name for name in ROUTES if name not in routes]
    if missing:
        raise SystemExit(f"The contract has no route {missing}.")
    schemas: dict[str, Any] = {}
    for name, keys in FIELDS.items():
        schema = contract["components"]["schemas"].get(name)
        if schema is None:
            raise SystemExit(f"The contract has no schema {name!r}.")
        absent = [key for key in keys if key not in schema.get("properties", {})]
        if absent:
            raise SystemExit(f"The schema {name!r} of the contract has no field {absent}.")
        required = set(schema.get("required", []))
        schemas[name] = {
            key: {**_field(schema["properties"][key]), "required": key in required} for key in keys
        }
    return {"routes": dict(sorted(routes.items())), "schemas": schemas}


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("usage: python tests/contract/extract.py path/to/openapi.json")
    raw = Path(argv[1]).read_bytes()
    contract = json.loads(raw)
    extracted = {
        "generated_from": {
            "version": contract["info"]["version"],
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
        **extract(contract),
    }
    text = json.dumps(extracted, indent=1, sort_keys=False) + "\n"
    TARGET.write_text(text, encoding="utf-8", newline="\n")
    print(f"{TARGET}: {len(extracted['routes'])} routes, {len(extracted['schemas'])} schemas")


if __name__ == "__main__":
    main(sys.argv)
