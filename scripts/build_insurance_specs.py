#!/usr/bin/env python3
"""Insurance bundle から Context Mesh 用の OpenAPI 3.0.3 を生成する。"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


# Context Mesh のデモで公開する操作だけを列挙する。
OPERATION_ALLOWLIST = {
    "product": {("/products", "get"), ("/products/{product_id}", "get")},
    "customer": {("/customers", "get"), ("/customers/{customer_id}", "get")},
    "simulation": {("/simulations", "post")},
    "application": {("/applications", "get"), ("/applications/{application_id}", "get")},
    "policy": {("/policies", "get"), ("/policies/{policy_id}", "get")},
    "claim": {("/claims", "get"), ("/claims/{claim_id}", "get")},
}

# OpenAPI 3.1 / JSON Schema の構文を 3.0.3 相当へ写す規則。
CONVERSION_RULES = {
    "nullable_union": "anyOf/oneOf の null 分岐を除き、nullable: true を付ける。$ref は allOf で包む",
    "nullable_type": "type 配列の null を除き、nullable: true を付ける",
    "schema_examples": "schema の examples 配列の先頭を example にする",
    "const": "const を同じ値の単一要素 enum にする",
    "schema_markers": "$schema を削除し、最上位の webhooks/jsonSchemaDialect を削除する",
}

SERVICE_ORDER = ("product", "customer", "simulation", "application", "policy", "claim")
METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}


def read_yaml(path, yq):
    result = subprocess.run(
        [yq, "-o=json", ".", str(path)], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return json.loads(result.stdout)


def convert_schema(node):
    """再帰的に 3.1 の schema 構文を 3.0.3 表現へ変換する。"""
    if isinstance(node, list):
        return [convert_schema(item) for item in node]
    if not isinstance(node, dict):
        return node

    out = {}
    null_union = False
    for key, value in node.items():
        if key == "$schema":
            continue
        if key == "const":
            out["enum"] = [value]
            continue
        if key == "examples":
            # Schema の examples は配列。Media Type の examples は名前付き map なので保持する。
            if isinstance(value, list):
                if value:
                    out["example"] = convert_schema(value[0])
            else:
                out[key] = convert_schema(value)
            continue
        if key in ("anyOf", "oneOf") and isinstance(value, list):
            branches = [branch for branch in value if not (isinstance(branch, dict) and branch.get("type") == "null")]
            if len(branches) != len(value):
                null_union = True
                if len(branches) == 1:
                    branch = convert_schema(branches[0])
                    if "$ref" in branch:
                        out["allOf"] = [branch]
                    else:
                        for branch_key, branch_value in branch.items():
                            out[branch_key] = branch_value
                elif branches:
                    out[key] = [convert_schema(branch) for branch in branches]
            else:
                out[key] = [convert_schema(branch) for branch in value]
            continue
        if key == "type" and isinstance(value, list) and "null" in value:
            non_null = [item for item in value if item != "null"]
            out[key] = non_null[0] if len(non_null) == 1 else non_null
            null_union = True
            continue
        out[key] = convert_schema(value)
    if null_union:
        out["nullable"] = True
    return out


def refs_in(value):
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/"):
            yield ref
        for child in value.values():
            yield from refs_in(child)
    elif isinstance(value, list):
        for child in value:
            yield from refs_in(child)


def prune_components(spec):
    components = spec.get("components", {})
    if not components:
        spec.pop("components", None)
        return
    kept = set()
    pending = list(refs_in(spec.get("paths", {})))
    while pending:
        ref = pending.pop()
        if ref in kept:
            continue
        kept.add(ref)
        target = spec
        try:
            for part in ref[2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError):
            continue
        pending.extend(refs_in(target))
    pruned = {}
    for group, entries in components.items():
        selected = {name: item for name, item in entries.items() if f"#/components/{group}/{name}" in kept}
        if selected:
            pruned[group] = selected
    if pruned:
        spec["components"] = pruned
    else:
        spec.pop("components", None)


def build_spec(bundle_root, service, yq):
    source = read_yaml(bundle_root / "services" / service / "openapi.yaml", yq)
    paths = {}
    for path, path_item in source.get("paths", {}).items():
        kept_item = {}
        for key, value in path_item.items():
            if key.lower() in METHODS:
                if (path, key.lower()) in OPERATION_ALLOWLIST[service]:
                    kept_item[key] = value
            else:
                kept_item[key] = value
        if kept_item and any(key.lower() in METHODS for key in kept_item):
            paths[path] = kept_item

    # 元のトップレベル順を保ち、servers と paths だけデモ用に置き換える。
    spec = {}
    for key, value in source.items():
        if key in ("webhooks", "jsonSchemaDialect", "$schema"):
            continue
        if key == "openapi":
            spec[key] = "3.0.3"
        elif key == "info":
            info = dict(value)
            original = info.get("description", "")
            note = "デモ用に bundle v0.1.1 から必要な操作だけを抽出した仕様です。"
            info["description"] = (original.rstrip() + "\n\n" + note).strip()
            spec[key] = info
        elif key == "servers":
            spec[key] = [{
                "url": f"http://{service}.insurance.svc.cluster.local:8000",
                "description": "Insurance API サービスへのクラスタ内接続先です。",
            }]
        elif key == "paths":
            spec[key] = paths
        else:
            spec[key] = value
    if "servers" not in spec:
        spec["servers"] = [{"url": f"http://{service}.insurance.svc.cluster.local:8000", "description": "Insurance API サービスへのクラスタ内接続先です。"}]
    spec["paths"] = {path: {key: convert_schema(value) for key, value in item.items()} for path, item in spec.get("paths", {}).items()}
    for key in ("components",):
        if key in spec:
            spec[key] = convert_schema(spec[key])
    prune_components(spec)
    return spec


def generate(bundle_root, yq):
    outputs = {}
    ids = {}
    for service in SERVICE_ORDER:
        spec = build_spec(bundle_root, service, yq)
        for path, item in spec.get("paths", {}).items():
            for method, operation in item.items():
                if method.lower() not in METHODS:
                    continue
                op_id = operation.get("operationId")
                if op_id:
                    if op_id in ids:
                        raise ValueError(f"operationId collision: {op_id} ({ids[op_id]} and {service}:{method.upper()} {path})")
                    ids[op_id] = f"{service}:{method.upper()} {path}"
        outputs[Path("insurance/openapi") / f"{service}.json"] = json.dumps(spec, ensure_ascii=False, indent=2) + "\n"
    return outputs


def main():
    parser = argparse.ArgumentParser(description="Insurance bundle からデモ用 OpenAPI JSON を生成します。")
    parser.add_argument("--bundle-root", required=True, type=Path, help="kong-api-bundle-insurance のルート")
    parser.add_argument("--check", action="store_true", help="生成結果とコミット済みファイルを比較する")
    parser.add_argument("--yq", default="/opt/homebrew/bin/yq", help="YAML を JSON に変換する yq v4 CLI のパス")
    args = parser.parse_args()
    outputs = generate(args.bundle_root, args.yq)
    root = Path(__file__).resolve().parent.parent
    if args.check:
        different = [str(rel) for rel, content in outputs.items() if not (root / rel).is_file() or (root / rel).read_text(encoding="utf-8") != content]
        if different:
            print("差分のあるファイル:", file=sys.stderr)
            print("\n".join(different), file=sys.stderr)
            return 1
        print("Insurance の OpenAPI 仕様はすべて最新です。")
        return 0
    for rel, content in outputs.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"生成: {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
