#!/usr/bin/env python3
"""Apply the WildKernels BBRv3 backport after re-anchoring hunks that drifted.

The upstream patch (common/bbrv3/0001-net-tcp-backport-BBRv3-to-android16-6.12.patch)
is written against a slightly older 6.12 tree. Two hunks no longer match this
kernel:

  net/ipv4/Kconfig
      upstream context ends with `default DEFAULT_CUBIC`; this tree already
      defaults to BBR. The BBR3 block itself still goes in the same place.

  net/ipv4/tcp_input.c
      this tree calls tcp_in_ack_event() between tcp_rack_update_reo_wnd()
      and the TLP check, a line the patch does not list as context.

Both are context-only differences. The script rewrites those context lines,
fixes the `DEFAULT_BBR` typo on the bbr3 default string, then applies the
result with `git apply`. Usage: bbrv3_compat.py <kernel/common> <patch>
"""
import re
import subprocess
import sys
from pathlib import Path


def split_sections(text):
    return re.split(r"(?=^diff --git )", text, flags=re.M)


def adapt_kconfig(section):
    # the tree defaults to BBR, the patch expects CUBIC in this context line
    section = section.replace(
        " \tdefault DEFAULT_CUBIC\n", " \tdefault DEFAULT_BBR\n", 1
    )
    # this tree's last string default is bbr, the patch expects cubic
    section = section.replace(
        ' \tdefault "cubic"\n', ' \tdefault "bbr"\n', 1
    )
    # upstream typo: the bbr3 string default tests DEFAULT_BBR
    section = section.replace(
        '+\tdefault "bbr3" if DEFAULT_BBR\n',
        '+\tdefault "bbr3" if DEFAULT_BBR3\n',
        1,
    )
    return section


def adapt_tcp_input(section):
    hunks = re.split(r"(?=^@@ )", section, flags=re.M)
    for i, hunk in enumerate(hunks):
        if not hunk.startswith("@@ -4049,7 +4079,7 @@"):
            continue
        old = (
            " \ttcp_rack_update_reo_wnd(sk, &rs);\n"
            " \n"
            " \tif (tp->tlp_high_seq)\n"
        )
        new = (
            " \ttcp_rack_update_reo_wnd(sk, &rs);\n"
            " \n"
            " \ttcp_in_ack_event(sk, flag);\n"
            " \n"
            " \tif (tp->tlp_high_seq)\n"
        )
        if hunk.count(old) != 1:
            raise SystemExit(
                "unexpected tcp_input tcp_process_tlp_ack hunk shape"
            )
        hunk = hunk.replace(old, new, 1)
        hunk = hunk.replace(
            "@@ -4049,7 +4079,7 @@", "@@ -4049,9 +4079,9 @@", 1
        )
        hunks[i] = hunk
        return "".join(hunks)
    raise SystemExit("could not find the tcp_input hunk at 4049/4079")


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: bbrv3_compat.py <kernel/common> <patch>")

    tree = Path(sys.argv[1])
    patch = Path(sys.argv[2])
    out = []

    for section in split_sections(patch.read_text()):
        if section.startswith("diff --git a/net/ipv4/Kconfig "):
            section = adapt_kconfig(section)
        elif section.startswith("diff --git a/net/ipv4/tcp_input.c "):
            section = adapt_tcp_input(section)
        out.append(section)

    adapted = tree / ".bbrv3-adapted.patch"
    adapted.write_text("".join(out))

    try:
        subprocess.run(
            ["git", "apply", "--whitespace=nowarn", "--check", str(adapted)],
            cwd=tree,
            check=True,
        )
        subprocess.run(
            ["git", "apply", "--whitespace=nowarn", str(adapted)],
            cwd=tree,
            check=True,
        )
    finally:
        adapted.unlink(missing_ok=True)

    print("BBRv3 patch applied")


if __name__ == "__main__":
    main()