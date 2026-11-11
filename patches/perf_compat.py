#!/usr/bin/env python3
"""Two performance patches applied by anchor instead of by diff.

Both upstream patch files in WildKernels/kernel_patches were written against an
older 6.12 tree, so their context no longer matches this kernel even though the
change itself is one line:

  clear_page_16bytes_align.patch
      this tree names the function __pi_clear_page, so the patch's
      SYM_FUNC_START_PI(clear_page) context misses. Insert `.p2align 4` before
      the real entry point.

  increase_sk_mem_packets.patch
      only the value changed; the surrounding block moved.

Idempotent. Usage: perf_compat.py <kernel/common>
"""
import re
import sys
from pathlib import Path


def align_clear_page(tree):
    path = tree / "arch/arm64/lib/clear_page.S"
    if not path.exists():
        print("skip clear_page: file missing")
        return
    src = path.read_text()
    anchor = "SYM_FUNC_START(__pi_clear_page)"
    if "\t.p2align 4\n" + anchor in src:
        print("= clear_page already aligned")
        return
    if src.count(anchor) != 1:
        print("skip clear_page: unexpected entry point shape")
        return
    path.write_text(src.replace(anchor, "\t.p2align 4\n" + anchor, 1))
    print("+ clear_page 16-byte align")


def increase_sk_mem(tree):
    path = tree / "include/net/sock.h"
    if not path.exists():
        print("skip increase_sk_mem_packets: file missing")
        return
    src = path.read_text()
    if "#define _SK_MEM_PACKETS\t\t1024" in src:
        print("= increase_sk_mem_packets already applied")
        return
    pattern = re.compile(r"(?m)^#define _SK_MEM_PACKETS[ \t]+256$")
    if len(pattern.findall(src)) != 1:
        print("skip increase_sk_mem_packets: anchor not unique")
        return
    path.write_text(
        pattern.sub("#define _SK_MEM_PACKETS\t\t1024", src, count=1)
    )
    print("+ increase_sk_mem_packets 256 -> 1024")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: perf_compat.py <kernel/common>")
    tree = Path(sys.argv[1])
    align_clear_page(tree)
    increase_sk_mem(tree)


if __name__ == "__main__":
    main()