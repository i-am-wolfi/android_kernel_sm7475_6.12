#!/usr/bin/env python3
"""Patches de porte marble/diwali aplicados sobre a tree no runner.
Idempotente: so aplica se o padrao original existir. Uso: cd kernel && python3 fixups.py
"""
import re
import sys


def patch_tzmem_enum(text):
    """qcom_tzmem.h: enum bridge_owner so existe com SHMBRIDGE, mas o ramo
    #else o usa -> erro com MODE_GENERIC. Sobe o enum para fora do #if."""
    pat = re.compile(
        r'(#if IS_ENABLED\(CONFIG_QCOM_TZMEM_MODE_SHMBRIDGE\)\n+)'
        r'(enum bridge_owner \{.*?\n\};)',
        re.S,
    )
    m = pat.search(text)
    if not m:
        return text, False
    return pat.sub(lambda mo: mo.group(2) + '\n' + mo.group(1), text, count=1), True


FIXES = [
    ('drivers/firmware/qcom/qcom_tzmem.h', patch_tzmem_enum),
]

if __name__ == '__main__':
    for path, fn in FIXES:
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                orig = f.read()
        except OSError:
            print('SKIP %s (ausente)' % path)
            continue
        new, changed = fn(orig)
        if changed:
            with open(path, 'w') as f:
                f.write(new)
            print('PATCH %s' % path)
        else:
            print('OK %s (ja aplicado ou padrao ausente)' % path)
