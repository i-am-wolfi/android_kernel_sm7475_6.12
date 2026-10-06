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

# Makefiles ESTRUTURAIS (fluxo de build: vmlinux, boot, config targets,
# device-tree top-level): nunca fundir. A tree compila com os dela.
SKIP_EXACT = {
    './Makefile', './Kbuild',
    './arch/arm64/Makefile', './arch/arm64/boot/Makefile',
    './scripts/Makefile',
}


def _skip(p):
    if p in SKIP_EXACT:
        return True
    # nada em boot/dts (o dts/Makefile da tree e vendor-only de proposito)
    if '/boot/dts' in p:
        return True
    return False

# Objetos que a tree excluiu DE PROPOSITO (headers qcom incompativeis;
# nada na tree chama esses simbolos). Nao ressuscitar.
# - rpm-traces.o: pm.h da tree removeu usage_count/disable_depth e
#   runtime.c nao chama trace_rpm_*.
DENY_OBJS = {'rpm-traces.o'}

# Linha obj-/lib-: sufixo arbitrario, inclui funcoes make com espaco e
# virgula (ex obj-$(subst m,y,$(CONFIG_MMC)) += host/) e atribuicao inicial
# com '=' (ex obj-y = fork.o panic.o \ + continuacoes, usada nos Makefiles
# centrais kernel/mm/fs). Grupos: 1=obj|lib 2=sufixo 3=op 4=rhs.
# O op exige espaco depois (senao '=' dentro de $(X=y) vira falso op).
OBJ_LINE = re.compile(r'^(obj|lib)\b(.*?)\s*(\+=|\?=|:=|=(?!=))\s+(.+?)\s*$')
# Mesma deteccao p/ busca multilinha (pm do parent)
OBJ_ANY = r'^(?:obj|lib)\b.*?(?:\+=|\?=|:=|=(?!=))\s+'

merged = 0
for root, dirs, files in os.walk('.'):
    if root.startswith(('./.git', './out')):
        dirs[:] = []
        continue
    for fn in files:
        if fn not in NAMES:
            continue
        kp = os.path.join(root, fn)
        if _skip(kp):
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
        have_tokens = set(re.findall(r'[\w][\w\-./]*/|[\w][\w\-./]*\.(?:o|a)\b', local))
        local_assigns = set(re.findall(r'(?m)^([^\s#:][^:]*?)\s*[:+?]?=', local))
        local_targets = set(x.strip() for x in re.findall(r'(?m)^([^\s#:][^:]*):', local))
        local_lines = set(l.strip() for l in local.splitlines())
        # divide base em unidades: linha col-0 + linhas tab seguintes (receita),
        # rastreando guardas ifneq/ifeq/ifdef/ifndef (preservadas ao anexar,
        # senao obj incondicional duplica simbolo no link, ex up.o vs smp.o)
        lines = base.splitlines(keepends=True)
        add = []
        i = 0
        guard = []
        def _wrap(u):
            if not guard:
                return u
            g = ''.join(g if g.endswith('\n') else g + '\n' for g in guard)
            return g + u + 'endif\n' * len(guard)

        def _push_guard(ln):
            guard.append(ln if ln.endswith('\n') else ln + '\n')

        while i < len(lines):
            ln = lines[i]
            if not re.match(r'^[^\s#]', ln):
                i += 1
                continue
            gm = re.match(r'^(ifneq|ifeq|ifdef|ifndef)\b', ln)
            if gm:
                _push_guard(ln)
                i += 1
                continue
            if re.match(r'^else\b', ln):
                if guard:
                    guard[-1] = guard[-1].rstrip('\n') + '\nelse\n'
                i += 1
                continue
            if re.match(r'^endif\b', ln):
                if guard:
                    guard.pop()
                i += 1
                continue
            unit = ln
            j = i + 1
            while j < len(lines) and lines[j].startswith((' ', '\t')):
                unit += lines[j]
                j += 1
            first = unit.split('\n', 1)[0].rstrip('\\').strip()
            m = OBJ_LINE.match(first)
            if m:
                # funde por token qualquer que seja o op ('+=', ':=', '=',
                # '?='): o anexo usa sempre '+=' (acrescenta sem
                # sobrescrever; apos ':=' o '+=' tambem avalia na hora).
                # Alem dos tokens planos (.o/.a, dir/), preserva refs a
                # vars/funcs no rhs (ex $(mmu-y), $(memory-hotplug-y)):
                # sem a linha consumidora, os DEFs (m15) entram mas os
                # objetos nunca linkam (undefined symbol no vmlinux).
                # rhs = tudo apos o op ja validado pelo OBJ_LINE (nao
                # re-procurar o op: sufixo pode conter '=' interno)
                after = first[m.end(3):]
                rest = after + '\n' + '\n'.join(unit.splitlines()[1:])
                refs = []
                for w in re.split(r'\s+', rest):
                    if '$' not in w or w == '\\':
                        continue
                    w2 = w[:-1] if w.endswith('\\') and len(w) > 1 else w
                    if w2 not in local and w2 not in refs:
                        refs.append(w2)
                # tokens planos fora das refs: foo.o dentro de
                # $(if $(C),foo.o) nao pode entrar incondicional
                plain_src = re.sub(r'[^\s]*\$[^\s]*', ' ', unit)
                toks = re.findall(r'[\w][\w\-./]*/|[\w][\w\-./]*\.(?:o|a)\b', plain_src)
                denied = [t for t in toks if t in DENY_OBJS]
                if denied:
                    print('DENY %s: %s' % (kp, denied))
                new_toks = [t for t in toks if t not in have_tokens and t not in DENY_OBJS]
                if new_toks or refs:
                    if refs and not new_toks:
                        print('REFS %s: %s' % (kp, refs[:4]))
                    prefix = '%s%s += ' % (m.group(1), m.group(2))
                    add.append(_wrap(prefix + ' '.join(new_toks + refs) + '\n'))
                i = j
                continue
            # vars compostas (foo-objs, foo-y, foo-$(CONFIG..)): definem conteudo
            # de objeto linkado; vao junto com o obj- correspondente (senao
            # "No rule"). So se a var nao existe no local. Nunca flags.
            m15 = re.match(r'^([\w\-\./$(){}]+?)\s*(\+=|:=|=|\?=)\s*(.+?)\s*$', first)
            if m15 and re.search(r'-(?:objs|y)(?:-|$|\s)|\-\$\(CONFIG', m15.group(1)) and not re.match(r'^(ccflags|asflags|ldflags|cppflags|cflags|aflags|rustflags|bindgen|rtoflags)', m15.group(1)):
                varname = re.sub(r'\s+', '', m15.group(1))
                if varname not in local_assigns:
                    add.append(_wrap(unit if unit.endswith('\n') else unit + '\n'))
                i = j
                continue
            m2 = re.match(r'^((?:hostprogs|targets|always|extra|clean-files|cmd_\w+|quiet_cmd_\w+))(?:-[\w$(){}]+)?\s*(\+=|:=|=|\?=)\s*(.*)$', first)
            if m2:
                var, op = m2.group(1), m2.group(2)
                if op == '+=':
                    if first.strip() not in local_lines:
                        add.append(_wrap(unit if unit.endswith('\n') else unit + '\n'))
                elif var not in local_assigns:
                    add.append(_wrap(unit if unit.endswith('\n') else unit + '\n'))
                i = j
                continue
            m3 = re.match(r'^([^\s#:][^:]*):', first)
            if m3 and '%' not in first.split(':')[0] and 'clean' not in first.split(':')[0] and '.PHONY' not in unit:
                # nunca diretivas make (ifdef/ifeq/ifneq/ifndef/else/endif/define/...):
                # um ':' dentro de $(...) nao faz disso uma regra (ex ifneq $(words $(subst :, ...)))
                if re.match(r'^(ifdef|ifndef|ifeq|ifneq|else|endif|define|endef|export|unexport|private|override|include|-include|vpath|\.PHONY|undefine)\b', first):
                    i = j
                    continue
                tgt = m3.group(1).strip()
                if tgt not in local_targets:
                    add.append(_wrap(unit if unit.endswith('\n') else unit + '\n'))
                i = j
                continue
            i = j
        if add:
            with open(kp, 'w') as f:
                f.write(local + '\n# --- marble: objs upstream restaurados ---\n' + ''.join(add))
            merged += 1
            print('MKEDGE %s (+%d linhas)' % (kp, len(add)))
print('mkmerged=%d' % merged)


def _obj_subdirs_of(makefile_path):
    """Conjunto de subdirs (ex 'regmap/') referenciados como alvo em obj-/lib-."""
    try:
        with open(makefile_path, encoding='utf-8', errors='replace') as f:
            text = f.read()
    except OSError:
        return set()
    out = set()
    for m in re.finditer(r'(?m)^(obj|lib)\b.*?(?:\+=|:=)\s*(.+?)\s*$', text):
        for t in re.findall(r'[\w][\w\-./]*/', m.group(2)):
            out.add(t)
    return out


fixed = 0
for root, dirs, files in os.walk('.'):
    if root.startswith(('./.git', './out')):
        dirs[:] = []
        continue
    for fn in files:
        if fn not in NAMES:
            continue
        kp = os.path.join(root, fn)
        try:
            with open(kp, encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except OSError:
            continue
        # guarda por linha (ifdef stack) p/ decisoes seguras
        guards = []
        g = 0
        for ln in lines:
            s = ln.strip()
            if re.match(r'^(ifneq|ifeq|ifdef|ifndef)\b', s):
                g += 1
            elif re.match(r'^endif\b', s):
                g = max(0, g - 1)
            guards.append(g)
        drop = set()
        # R1: linhas obj- exatas duplicadas, ambas sem guarda -> mantem a 1a
        seen = {}
        for idx, ln in enumerate(lines):
            s = ln.strip()
            if OBJ_LINE.match(s) and guards[idx] == 0:
                if s in seen:
                    drop.add(idx)
                    print('DUPELN %s: %s' % (kp, s[:90]))
                else:
                    seen[s] = idx
        # R2: deep D/sub/ + parent D/ (ambos sem guarda) e parent cobre sub/
        #     -> remove deep (senao mesma subdir desce 2x e duplica no link)
        subs = {}  # token -> [idx]
        for idx, ln in enumerate(lines):
            if guards[idx] > 0:
                continue
            m = OBJ_LINE.match(ln.strip())
            if not m:
                continue
            for t in re.findall(r'[\w][\w\-./]*/', m.group(4)):
                subs.setdefault(t, []).append(idx)
        for t, idxs in subs.items():
            inner = t.rstrip('/')
            if '/' not in inner:
                continue
            parent = inner.split('/')[0] + '/'
            if parent not in subs:
                continue
            mkparent = os.path.normpath(os.path.join(os.path.dirname(kp), parent, 'Makefile'))
            if not os.path.isfile(mkparent):
                continue
            try:
                with open(mkparent, encoding='utf-8', errors='replace') as f:
                    pm = f.read()
            except OSError:
                continue
            sub = inner.split('/')[1] + '/'
            if re.search(r'(?m)' + OBJ_ANY + r'.*?\b%s' % re.escape(sub), pm):
                for idx in idxs:
                    drop.add(idx)
                print('CONFIX %s: remove deep %s (coberto por %s)' % (kp, t, parent))
        if drop:
            with open(kp, 'w') as f:
                f.writelines([ln for idx, ln in enumerate(lines) if idx not in drop])
            fixed += 1
print('confix=%d' % fixed)
