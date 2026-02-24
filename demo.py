"""
demo.py — end-to-end example of the OAS hint extraction pipeline.

Loads a spec string → resolves $refs → runs all hint extractors →
prints results and shows how to build a prompt payload per section.

Run: python demo.py
"""

import json
from oas_hints.loader import load_oas_string
from oas_hints import extract_all_hints, Severity

# ── Sample spec with deliberate issues for demonstration ─────────────────────
SAMPLE_SPEC = """
openapi: "3.0.3"
info:
  title: my example api
  version: "not-semver"
  contact:
    name: Platform Team

paths:
  /Users:
    get:
      summary: "get users."
      responses:
        "200":
          description: Success
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: "#/components/schemas/User"
              examples:
                sample:
                  value:
                    id: 1
                    # Note: April only has 30 days — this would break yaml.safe_load
                    # but our NoDatesSafeLoader handles it gracefully
                    createdAt: "2025-04-31"

  /users/{userId}:
    get:
      operationId: getUser
      summary: Retrieve a user by ID
      description: Returns a single user matching the given userId.
      tags:
        - Users
      parameters:
        - name: userId
          in: path
          required: true
          description: The unique identifier for the user
          schema:
            type: integer
      responses:
        "200":
          description: User found
        "404":
          description: User not found

  /users/{userId}/orders:
    get:
      operationId: getUserOrders
      tags:
        - Users
      parameters:
        - name: userId
          in: path
          # required: true is missing — should be flagged
          description: User ID
          schema:
            type: integer
        - name: status
          in: query
          description: Filter by order status
          schema:
            type: string
            enum: [pending, shipped, delivered]
      responses:
        "200":
          description: List of orders

components:
  schemas:
    User:
      type: object
      description: Represents a user account
      required:
        - id
        - email
        - nonExistentField
      properties:
        id:
          type: integer
          description: Unique user identifier
        email:
          type: string
          format: email
          description: User email address
        username:
          type: string
          # No description — should be flagged
        tags:
          type: array
          # items missing — should be flagged

    order_response:
      # Name not PascalCase — should be flagged
      type: object
      properties:
        orderId:
          type: integer
        amount:
          type: number
"""


def run_demo():
    print("=" * 70)
    print("OAS HINT EXTRACTION DEMO")
    print("=" * 70)

    # ── Load and resolve ──────────────────────────────────────────────────────
    spec, errors = load_oas_string(SAMPLE_SPEC)

    if errors:
        print("\n⚠  LOADER ERRORS:")
        for err in errors:
            print(f"   {err}")

    if spec is None:
        print("Could not load spec — aborting.")
        return

    print(f"\n✓  Spec loaded successfully")
    print(f"   OAS version : {spec.get('openapi')}")
    print(f"   Title       : {spec.get('info', {}).get('title')}")
    print(f"   Paths       : {len(spec.get('paths', {}))}")

    # ── Run all hint extractors ───────────────────────────────────────────────
    all_hints = extract_all_hints(spec)

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("HINT SUMMARY BY SECTION")
    print("=" * 70)

    total = 0
    for section_name, payload in all_hints.items():
        by_severity = {s: 0 for s in Severity}
        for h in payload.hints:
            by_severity[h.severity] += 1

        count = len(payload.hints)
        total += count
        errors_n   = by_severity[Severity.ERROR]
        warnings_n = by_severity[Severity.WARNING]
        info_n     = by_severity[Severity.INFO]

        print(f"\n  {section_name.upper():15s}  "
              f"{count:3d} hints  "
              f"[E:{errors_n}  W:{warnings_n}  I:{info_n}]")

        for h in payload.hints:
            icon = {"error": "✗", "warning": "△", "info": "ℹ"}[h.severity]
            print(f"    {icon}  {h.location}")
            print(f"       {h.message}")

    print(f"\n  {'TOTAL':15s}  {total:3d} hints")

    # ── Show prompt payload example for one section ───────────────────────────
    print("\n" + "=" * 70)
    print("EXAMPLE PROMPT PAYLOAD (parameters section)")
    print("=" * 70)

    params_payload = all_hints["parameters"]

    prompt = f"""You are reviewing API parameters against our quality standards.

PARAMETER INVENTORY ({len(params_payload.raw_data)} parameters found):
{params_payload.hints_block()}

RAW PARAMETER DATA:
{json.dumps(params_payload.raw_data, indent=2)}

QUESTIONS:
[Your rule-specific questions go here]
"""
    # Print first 1200 chars to keep demo output readable
    print(prompt[:1200] + "\n... [truncated for demo]")


if __name__ == "__main__":
    run_demo()
