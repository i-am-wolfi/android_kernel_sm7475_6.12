#!/usr/bin/env python3
"""Merge Makefiles/Kbuild: base upstream + linhas obj- ausentes na tree.
A tree (kleaf) esvaziou Makefiles (ex lib/Makefile com 2 objs); o make
precisa das listas completas. Nunca remove nada da tree; so acrescenta
objetos/dirs nao mencionados. Uso: cd kernel && python3 merge-makefiles.py ../ack-src
"""
import os
import re
import sys

UPSTREAM = sys.argv[1] if len(sys.argv) > 1 else '../ack-src'
NAMES = ('Makefile', 'Kbuild')

merged = 0
for root, dirs, files in os.walk('.'):
    if root.startswith(('./.git', './out')):
        dirs[:] = []
        continue
    for fn in files:
        if fn not in NAMES:
            continue
        kp = os.path.join(root, fn)
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
        # alvos ja mencionados no arquivo local (obj/modulo/dir)
        have_tokens = set(re.findall(r'[\w][\w\-./]*/|[\w][\w\-./]*\.(?:o|a)\b', local))
        # lib-y (:=) so entra se o local nao define nenhum (senao sobrescreveria)
        local_has_liby = bool(re.search(r'(?m)^lib-y\s*[:+?]?=', local))
        add = []
        for ln in base.splitlines(keepends=True):
            m = re.match(r'^(obj|lib)(?:-[\w$(){}]+)?\s*(\+=|:=)\s*(.+?)\s*$', ln)
            if not m:
                continue
            if m.group(2) == ':=' and (m.group(1) != 'lib' or local_has_liby):
                continue
            rhs = m.group(3)
            toks = re.findall(r'[\w][\w\-./]*/|[\w][\w\-./]*\.(?:o|a)\b', rhs)
            if not toks:
                continue
            if any(t in have_tokens for t in toks):
                continue
            add.append(ln if ln.endswith('\n') else ln + '\n')
        if add:
            with open(kp, 'w') as f:
                f.write(local + '\n# --- marble: objs upstream restaurados ---\n' + ''.join(add))
            merged += 1
            print('MKEDGE %s (+%d linhas)' % (kp, len(add)))
print('mkmerged=%d' % merged)
