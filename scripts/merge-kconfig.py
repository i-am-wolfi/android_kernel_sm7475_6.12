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


def resolve_src(t, srcdir):
    """source paths no Kconfig sao relativos a raiz (srctree); tenta cru, senao relativo ao dir."""
    t = t.replace('$(KCONFIG_EXT_PREFIX)', '').replace('$(SRCARCH)', 'arm64')
    if os.path.exists(t):
        return os.path.normpath(t)
    j = os.path.normpath(os.path.join(srcdir, t))
    if os.path.exists(j):
        return j
    return None


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
        if kp.startswith('arch/') and not (kp == 'arch/Kconfig' or kp.startswith('arch/arm64/')):
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
        base_srcs = set()
        for s in sources_of(base):
            r0 = resolve_src(s, os.path.dirname(kp))
            if r0:
                base_srcs.add(r0)
        add_src, seen = [], set()
        for s in sources_of(local):
            r = resolve_src(s, os.path.dirname(kp))
            if r is None or r in base_srcs or r in seen:
                continue
            seen.add(r)
            add_src.append('source "%s"\n' % r)
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


def dedupe_sources():
    """Remove arestas source duplicadas (mesmo alvo via 2+ arquivos).
    Plain make nao tolera double-parse (prompts duplicados quebram choices).
    So considera arquivos VIVOS no parse arm64: ignora Kconfig.msm/qtvm
    (nunca sourced no make) e arch/<outras> (nunca parseadas p/ arm64).
    Mantem a aresta do diretorio-pai do alvo; remove das demais. Loga tudo.
    """
    import glob

    def live(p):
        if os.path.basename(p) in ('Kconfig.msm', 'Kconfig.qtvm'):
            return False
        if p.startswith('arch/') and not (p == 'arch/Kconfig' or p.startswith('arch/arm64/')):
            return False
        return True

    edges = {}  # target_tree_rel -> set(sourcer)
    src_lines = {}  # (sourcer, target) -> [linenos]

    files = []
    for root, dirs, fns in os.walk('.'):
        if root.startswith(('./.git', './out')):
            dirs[:] = []
            continue
        for fn in fns:
            if fn == 'Kconfig' or fn.startswith('Kconfig'):
                files.append(os.path.join(root, fn))
    for kp in files:
        if not live(kp):
            continue
        try:
            with open(kp, encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except OSError:
            continue
        srcdir = os.path.dirname(kp)
        for i, ln in enumerate(lines):
            m = re.match(r'^\s*source\s+"([^"]+)"', ln)
            if not m:
                continue
            t = resolve_src(m.group(1), srcdir)
            if t is None:
                continue
            edges.setdefault(t, set()).add(kp)
            src_lines.setdefault((kp, t), []).append(i)
    fixed = 0
    for t, sourcers in sorted(edges.items()):
        sourcers = set(s for s in sourcers if live(s))
        if len(sourcers) < 2:
            continue
        parent = os.path.join(os.path.dirname(t), 'Kconfig')
        keep = parent if parent in sourcers else sorted(sourcers)[0]
        for s in sorted(sourcers):
            if s == keep:
                continue
            with open(s, encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
            kept, removed = [], 0
            for ln in lines:
                m = re.match(r'^\s*source\s+"([^"]+)"', ln)
                if m and resolve_src(m.group(1), os.path.dirname(s)) == t:
                    removed += 1
                    continue
                kept.append(ln)
            if removed:
                with open(s, 'w') as f:
                    f.writelines(kept)
                fixed += 1
                print('DEDUP %s: remove source (mantido em %s)' % (s, keep))
    print('dedup_fixed=%d' % fixed)


dedupe_sources()
