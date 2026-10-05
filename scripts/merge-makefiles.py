#!/usr/bin/env python3
"""Merge Makefiles/Kbuild: base upstream + o que falta na tree, sem duplicar.

A tree (kleaf) esvaziou Makefiles e removeu regras de geracao; o make
precisa das listas completas. Nunca remove nada da tree; so acrescenta:
- linhas obj-/lib- com alvos nao mencionados;
- linhas hostprogs/targets/always/extra/clean-files/cmd_/quiet_cmd_ ausentes;
- blocos de regra (alvo: + receita) para alvos ausentes (gera oid_registry,
  crc32table, etc).
Nao toca em ifdef/include/export/define (estrutura).
Uso: cd kernel && python3 merge-makefiles.py ../ack-src
"""
import os
import re
import sys

UPSTREAM = sys.argv[1] if len(sys.argv) > 1 else '../ack-src'
NAMES = ('Makefile', 'Kbuild')

# Objetos que a tree excluiu DE PROPOSITO (headers qcom incompativeis;
# nada na tree chama esses simbolos). Nao ressuscitar.
# - rpm-traces.o: pm.h da tree removeu usage_count/disable_depth e
#   runtime.c nao chama trace_rpm_*.
DENY_OBJS = {'rpm-traces.o'}

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
        have_tokens = set(re.findall(r'[\w][\w\-./]*/|[\w][\w\-./]*\.(?:o|a)\b', local))
        local_assigns = set(re.findall(r'(?m)^([A-Za-z0-9_]+)\s*[:+?]?=', local))
        local_targets = set(re.findall(r'(?m)^([^\s#:][^:]*):', local))
        local_has_liby = bool(re.search(r'(?m)^lib-y\s*[:+?]?=', local))
        local_lines = set(l.strip() for l in local.splitlines())
        # divide base em unidades: linha col-0 + linhas tab seguintes (receita)
        lines = base.splitlines(keepends=True)
        add = []
        i = 0
        while i < len(lines):
            ln = lines[i]
            if not re.match(r'^[^\s#]', ln):
                i += 1
                continue
            unit = ln
            j = i + 1
            while j < len(lines) and lines[j].startswith((' ', '\t')):
                unit += lines[j]
                j += 1
            first = unit.split('\n', 1)[0].rstrip('\\').strip()
            m = re.match(r'^(obj|lib)(?:-[\w$(){}]+)?\s*(\+=|:=)\s*(.+?)\s*$', first)
            if m:
                if not (m.group(2) == ':=' and (m.group(1) != 'lib' or local_has_liby)):
                    toks = re.findall(r'[\w][\w\-./]*/|[\w][\w\-./]*\.(?:o|a)\b', unit)
                    denied = [t for t in toks if t in DENY_OBJS]
                    if denied:
                        print('DENY %s: %s' % (kp, denied))
                    new_toks = [t for t in toks if t not in have_tokens and t not in DENY_OBJS]
                    if new_toks:
                        prefix = re.match(r'^((?:obj|lib)(?:-[\w$(){}]+)?\s*(?:\+=|:=)\s*)', first).group(1)
                        add.append(prefix + ' '.join(new_toks) + '\n')
                i = j
                continue
            m2 = re.match(r'^((?:hostprogs|targets|always|extra|clean-files|cmd_\w+|quiet_cmd_\w+))(?:-[\w$(){}]+)?\s*(\+=|:=|=|\?=)\s*(.*)$', first)
            if m2:
                var, op = m2.group(1), m2.group(2)
                if op == '+=':
                    if first.strip() not in local_lines:
                        add.append(unit if unit.endswith('\n') else unit + '\n')
                elif var not in local_assigns:
                    add.append(unit if unit.endswith('\n') else unit + '\n')
                i = j
                continue
            m3 = re.match(r'^([^\s#:][^:]*):', first)
            if m3 and '%' not in first.split(':')[0] and 'clean' not in first.split(':')[0] and 'FORCE' not in unit and '.PHONY' not in unit:
                # nunca diretivas make (ifdef/ifeq/ifneq/ifndef/else/endif/define/...):
                # um ':' dentro de $(...) nao faz disso uma regra (ex ifneq $(words $(subst :, ...)))
                if re.match(r'^(ifdef|ifndef|ifeq|ifneq|else|endif|define|endef|export|unexport|private|override|include|-include|vpath|\.PHONY|undefine)\b', first):
                    i = j
                    continue
                tgt = m3.group(1).strip()
                if tgt not in local_targets:
                    add.append(unit if unit.endswith('\n') else unit + '\n')
                i = j
                continue
            i = j
        if add:
            with open(kp, 'w') as f:
                f.write(local + '\n# --- marble: objs upstream restaurados ---\n' + ''.join(add))
            merged += 1
            print('MKEDGE %s (+%d linhas)' % (kp, len(add)))
print('mkmerged=%d' % merged)
