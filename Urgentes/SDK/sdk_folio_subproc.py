# -*- coding: utf-8 -*-
import os, sys, json, argparse
from sdk.loader import get_sdk, SDKError, SDKNotFound, SDKArchMismatch

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sdk-dir", required=True)
    p.add_argument("--empresa", required=True)
    p.add_argument("--concepto", required=True)
    p.add_argument("--serie", required=True)
    args = p.parse_args()

    try:
        sdk = get_sdk(args.sdk_dir)
    except Exception as e:
        print(json.dumps({"rc": 99901, "error": f"SDK: {e}"}))
        return 1

    rc = sdk.dll.open_company(args.empresa)
    if rc != 0:
        print(json.dumps({"rc": rc, "error": sdk.dll.error_text(rc)}))
        return 2

    rc, folio = sdk.dll.next_folio(args.concepto, args.serie)
    if rc != 0:
        print(json.dumps({"rc": rc, "error": sdk.dll.error_text(rc)}))
        return 3

    print(json.dumps({"rc": 0, "folio": folio}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
