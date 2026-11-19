import argparse
import json
import sys

import core


def main():
    ap = argparse.ArgumentParser(description="feishu base -> dida365 one-way sync")
    ap.add_argument("--run", action="store_true", help="actually write to dida365")
    ap.add_argument("--json", action="store_true", help="print raw json")
    ap.add_argument("--limit", type=int, default=0, help="only execute first N planned items (LIVE trial)")
    args = ap.parse_args()

    result = core.sync_once(run=args.run, limit=args.limit)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print("mode      : %s" % ("DRY-RUN" if result["dry_run"] else "LIVE"))
    print("scanned   : %d records (blank title skipped: %d)" %
          (result["scanned"], result.get("blank_skipped", 0)))
    print("plan      : create=%(create)d update=%(update)d skip=%(skip)d" % result["counts"])
    if args.limit > 0:
        print("limit     : only first %d items will be executed" % args.limit)
    if result["blockers"]:
        print("blockers  : " + ", ".join(result["blockers"]))
    for item in result["plan"][:args.limit or None]:
        if item["action"] != "skip":
            print("  [%s] %s" % (item["action"].upper(), item["title"]))
    if result["errors"]:
        for e in result["errors"]:
            print("  ERROR %s: %s" % (e["record_id"], e["error"]), file=sys.stderr)
    print("executed  : %d" % len(result["executed"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
