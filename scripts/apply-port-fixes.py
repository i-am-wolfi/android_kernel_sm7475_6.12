#!/usr/bin/env python3
"""Patches de porte marble/diwali aplicadas sobre a tree no runner.
Idempotente: so aplica se o padrao original existir. Uso: cd kernel && python3 fixups.py"""
import os
import sys


def patch_tzmem_robust(text):
    """Remove o #if IS_ENABLED(CONFIG_QCOM_TZMEM_MODE_SHMBRIDGE) do qcom_tzmem.h,
    ficando apenas o ramo #else (stubs inline). Isso evita erros 'unused function'
    com -Werror quando o config nao e setado para marble."""
    start_marker = '#if IS_ENABLED(CONFIG_QCOM_TZMEM_MODE_SHMBRIDGE)'
    end_marker = '#endif'

    start_idx = text.find(start_marker)
    if start_idx == -1:
        return text, False

    # Contar nesting para achar o #endif CORRETO (o primeiro apos o #else)
    # A estrutura eh: #if ... #else ... #endif (do shmbridge) depois #ifdef ... #endif (ffa) depois #endif (guard)
    # Queremos o #endif que fecha o bloco do shmbridge, que vem apos o #else

    # Encontrar o #else apos o #if
    else_pos = text.find('#else', start_idx + 1)
    if else_pos == -1:
        return text, False

    # Encontrar o #endif que fecha este bloco (o primeiro #endif depois do #else)
    # Vamos contar: depois do #else, quais #if/#endif encontramos?
    # A estrutura tem: #else -> (conteudo) -> #endif (do shmbridge) -> #ifdef (ffa) -> #endif (guard)
    # Queremos o primeiro #endif depois do #else
    depth = 0
    end_idx = -1
    for i in range(else_pos, len(text)):
        line = text[i]
        stripped = line.strip()
        if stripped.startswith('#if') and not stripped.startswith('#else') and not stripped.startswith('#endif'):
            depth += 1
        elif stripped.startswith('#else'):
            # segundo #else (do FFA) - nao afeta nossa contagem de profundidade para o primeiro
            pass
        elif stripped.startswith('#endif'):
            depth -= 1
            if depth <= 0:
                end_idx = i
                break

    if end_idx == -1:
        # Fallback: remove do #if ate o fim do que parece ser o bloco
        end_idx = text.find('#endif', start_idx)
        if end_idx == -1:
            return text, False

    # Novo texto: remove o #if ... #else ... #endif do shmbridge
    # Mantemos o #else e seu conteudo, mais um #endif final
    new_text = text[:start_idx]  # tudo antes do #if
    new_text += text[else_pos:]  # do #else ate o fim

    # Remove um #endif extra se estiver incluido acidentalmente
    # Procurar o primeiro #endif no novo texto
    first_endif = new_text.find('#endif')
    if first_endif != -1:
        # Mantenha ate o primeiro #endif, depois o descarta para o novo #endif ser adicionado
        new_text = new_text[:first_endif]

    # Adiciona #endif final se nao existir
    if '#endif' not in new_text.split('/*')[-1] if '/*' in new_text else new_text:
        new_text += '\n#endif'

    # Remove comentarios em branco extras
    return new_text, True


FIXES = [
    ('drivers/firmware/qcom/qcom_tzmem.h', patch_tzmem_robust),
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