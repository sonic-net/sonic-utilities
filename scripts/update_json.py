#! /usr/bin/env python

import os
import json
import argparse

TMP_SUFFIX = ".tmp"
BAK_SUFFIX = ".bak"

def dict_update(dst, patch):
    for k in patch:
        if type(patch[k]) == dict:
            dst[k] = dict_update(dst[k], patch[k])
        else:
            dst[k] = patch[k]
    return dst

def do_update(rcf, patchf):
    dst = {}
    patch = {}

    tmpf = rcf + TMP_SUFFIX
    bakf = rcf + BAK_SUFFIX

    with open(rcf, "r") as f:
        dst = json.load(f)

    with open(patchf, "r") as f:
        patch = json.load(f)

    dst = dict_update(dst, patch)

    with open(tmpf, "w") as f:
        json.dump(dst, f, indent = 4)

    os.rename(rcf, bakf)
    os.rename(tmpf, rcf)


def main():
    parser = argparse.ArgumentParser(description="Update JSON based file")
    parser.add_argument("-u", "--update", help="JSON file to be updated")
    parser.add_argument("-p", "--patch", help="JSON file holding patch")
    args = parser.parse_args()

    if not args.update or not args.patch:
        raise Exception("check usage")

    do_update(args.update, args.patch)

if __name__ == '__main__':
    main()


