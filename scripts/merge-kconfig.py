#!/usr/bin/env python3
"""Merge Kconfigs: base upstream + adicoes qcom unicas da tree (sem duplicar).
Uso: cd kernel && python3 merge-kconfig.py ../upstream-src
Mantem Kconfig.platforms/msm/qtvm e folhas qcom intactas.
"""
import os
import re
import sys

KEEP_NAMES = ('Kconfig.platforms', 'Kconfig.msm', 'Kconfig.qtvm')
UPSTREAM = sys.argv[1] if len(sys.argv) > 1 else '../upstream-src'


def top_blocks(text):
    """(kind, name, body): config|menuconfig fora de choice/if (menu e ok)."""
    out, guard, cur = [], 0, None
    for ln in text.splitlines(keepends=True):
        s = ln.strip()
        if re.match(r'^\s*(choice|if)\b', s):
            if cur:
                out.append(cur)
                cur = None
            guard += 1
            continue
        if re.match(r'^\s*(endchoice|endif)\b', s):
            guard = max(0, guard - 1)
            continue
        if re.match(r'^\s*(menu|endmenu)\b', s):
            if cur:
                out.append(cur)
                cur = None
            continue
        m = re.match(r'^\s*(config|menuconfig)\s+([A-Za-z0-9_]+)\b', s)
        if m and guard == 0:
            if cur:
                out.append(cur)
            cur = (m.group(1), m.group(2), ln)
        elif cur and (ln.startswith((' ', '\t')) or s.startswith(('help', '---help---')) or s == ''):
            cur = (cur[0], cur[1], cur[2] + ln)
        else:
            if cur:
                out.append(cur)
                cur = None
    if cur:
        out.append(cur)
    return out


def sources_of(text):
    return re.findall(r'^\s*source\s+"([^"]+)"', text, re.M)


merged = 0
for root, dirs, files in os.walk('.'):
    if root.startswith(('./.git', './out')):
        dirs[:] = []
        continue
    for fn in files:
        if fn != 'Kconfig' and not fn.startswith('Kconfig'):
            continue
        kp = os.path.join(root, fn)
        if kp.endswith(KEEP_NAMES):
            continue
        up = os.path.join(UPSTREAM, os.path.relpath(kp, '.'))
        if not os.path.isfile(up):
            continue
        try:
            with open(kp, encoding='utf-8', errors='replace') as f:
                local = f.read()
            with open(up, encoding='utf-8', errors='replace') as f:
                base = f.read()
        except OSError:
            continue
        if local == base:
            continue
        base_srcs = set(sources_of(base))
        add_src, seen = [], set()
        for s in sources_of(local):
            t = s.replace('$(KCONFIG_EXT_PREFIX)', '')
            full = os.path.normpath(os.path.join(os.path.dirname(kp), t))
            if t not in base_srcs and t not in seen and os.path.exists(full):
                seen.add(t)
                add_src.append('source "%s"\n' % t)
        add_blk = []
        for kind, name, body in top_blocks(local):
            if not re.search(r'(?m)^\s*(?:config|menuconfig)\s+%s\b' % re.escape(name), base):
                add_blk.append(body if body.endswith('\n') else body + '\n')
        if add_src or add_blk:
            extra = '\n# --- marble: qcom additions (merged) ---\n' + ''.join(add_src) + ''.join(add_blk)
            with open(kp, 'w') as f:
                f.write(base + extra)
            merged += 1
            print('MERGE %s (+%d src +%d blk)' % (kp, len(add_src), len(add_blk)))
print('merged=%d' % merged)
