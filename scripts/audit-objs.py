#!/usr/bin/env python3
"""Audita Makefiles: todo objeto listado tem fonte (.c/.S), regra de geracao,
variavel composta (-objs/-y) ou subdir correspondente? Reporta o que falta.
Nao compila nada: falha rapido (minutos) em vez de 30min de build.
Uso: cd kernel && python3 audit-objs.py [--strict]
Sem --strict: so reporta (exit 0). Com --strict: exit 1 se faltar algo.
"""
import os
import re
import sys

STRICT = '--strict' in sys.argv
missing = []


def logical_lines(text):
    lines = text.splitlines(keepends=True)
    out, buf = [], ''
    for ln in lines:
        s = ln.rstrip('\n')
        if s.endswith('\\'):
            buf += s[:-1]
            continue
        buf += s
        out.append(buf + '\n')
        buf = ''
    if buf:
        out.append(buf + '\n')
    return out


for root, dirs, files in os.walk('.'):
    if root.startswith(('./.git', './out')):
        dirs[:] = []
        continue
    for fn in files:
        if fn not in ('Makefile', 'Kbuild'):
            continue
        kp = os.path.join(root, fn)
        try:
            with open(kp, encoding='utf-8', errors='replace') as f:
                content = f.read()
        except OSError:
            continue
        gen_targets = set()
        for m in re.finditer(r'(?m)^([^\s#:][^:]*):', content):
            t = m.group(1).strip()
            if '%' not in t and 'clean' not in t and not t.startswith(('ifdef', 'ifndef', 'ifeq', 'ifneq', 'else', 'endif', 'define', 'endef', 'export', 'unexport', 'private', 'override', 'include', 'vpath', '.PHONY', 'undefine')):
                gen_targets.add(os.path.basename(t))
        guard = 0
        for unit in logical_lines(content):
            first = unit.split('\n', 1)[0].strip()
            if re.match(r'^(ifneq|ifeq|ifdef|ifndef)\b', first):
                guard += 1
                continue
            if re.match(r'^endif\b', first):
                guard = max(0, guard - 1)
                continue
            if re.match(r'^else\b', first):
                continue
            m = re.match(r'^(obj|lib)(?:-[\w$(){}]+)?\s*(?:\+=|:=)\s*(.+?)\s*$', first)
            if not m:
                continue
            for tok in re.findall(r'[\w][\w\-./]*/|[\w][\w\-./]*\.(?:o|a)\b', unit):
                base = os.path.basename(tok)
                stem = base[:-2] if base[-2:] in ('.o', '.a') else base
                d = os.path.dirname(tok)
                lookdir = os.path.normpath(os.path.join(root, d)) if d else root
                if any(os.path.isfile(os.path.join(lookdir, stem + e)) for e in ('.c', '.S', '.s')):
                    continue
                if base in gen_targets or stem in gen_targets:
                    continue
                if re.search(r'(?m)^%s\s*[:+?]?=' % re.escape(stem + '-objs'), content):
                    continue
                if re.search(r'(?m)^%s\s*[:+?]?=' % re.escape(stem + '-y'), content):
                    continue
                if os.path.isdir(os.path.join(lookdir, stem)):
                    continue
                missing.append('%s: %s (guard=%s)' % (kp, tok, guard > 0))

print('audit-objs: %d objetos sem fonte visivel' % len(missing))
for m in sorted(set(missing))[:150]:
    print('  MISSING', m)
sys.exit(1 if (STRICT and missing) else 0)
