#!/usr/bin/env python3
"""Patches de porte marble/diwali aplicados sobre a tree no runner.
Idempotente: so aplica se o padrao original existir. Uso: cd kernel && python3 fixups.py
"""
import re
import sys


def patch_tzmem_enum(text):
    """qcom_tzmem.h: enum bridge_owner so existe com SHMBRIDGE, mas o ramo
    #else o usa -> erro com MODE_GENERIC. Sobe o enum para fora do #if e
    marca os stubs do #else com __maybe_unused (nao usados no GENERIC)."""
    pat = re.compile(
        r'(#if IS_ENABLED\(CONFIG_QCOM_TZMEM_MODE_SHMBRIDGE\)\n+)'
        r'(enum bridge_owner \{.*?\n\};)',
        re.S,
    )
    m = pat.search(text)
    changed = False
    if m:
        text = pat.sub(lambda mo: mo.group(2) + '\n' + mo.group(1), text, count=1)
        changed = True
    for name in ('qcom_tzmem_pm_freeze', 'qcom_tzmem_pm_restore', 'qcom_tzmem_pm_thaw'):
        p2 = re.compile(r'static (inline )?int\s+(%s)\s*\(' % name)
        mm = p2.search(text)
        if mm and '__maybe_unused' not in text[max(0, mm.start() - 40):mm.start()]:
            text = p2.sub(r'static \1__maybe_unused int \2(', text)
            changed = True
    return text, changed


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
