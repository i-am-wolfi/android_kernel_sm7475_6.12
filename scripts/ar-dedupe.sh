#!/bin/sh
# ar-dedupe.sh: wrapper do llvm-ar que remove membros duplicados da mesma
# invocacao (mesmo path .o listado 2x por obj-y duplo apos merge de Makefiles).
# Mesmo path 2x == mesmo arquivo == seguro incluir uma vez so.
# So atua em operacoes de criacao/atualizacao (c/r/q); resto passa direto.
# Uso: make AR="/path/ar-dedupe.sh"
REAL_AR="llvm-ar"
op="$1"
case "$op" in
  *c*|*r*|*q*)
    ;; # criar/substituir/atualizar: filtra abaixo
  *)
    exec "$REAL_AR" "$@"
    ;;
esac
# acha o arquivo destino: primeiro arg sem '-' (pulando flags coladas tipo rcsD)
seen_out=""
archive=""
members=""
for a in "$@"; do
  case "$a" in
    -*) continue ;;
    @*) exec "$REAL_AR" "$@" ;;  # response file: nao mexe
    *)
      if [ -z "$archive" ]; then
        archive="$a"
      else
        members="$members $a"
      fi
      ;;
  esac
done
[ -n "$archive" ] || exec "$REAL_AR" "$@"
# filtra membros repetidos (normaliza ./ prefixo)
filtered=""
n=0
orig_n=0
for m in $members; do
  orig_n=$((orig_n + 1))
  key=$(printf '%s' "$m" | sed 's|^\./||')
  case " $seen_out " in
    *" $key "*) continue ;;
  esac
  seen_out="$seen_out $key"
  if [ -z "$filtered" ]; then
    filtered="$m"
  else
    filtered="$filtered $m"
  fi
  n=$((n + 1))
done
if [ "$n" -lt "$orig_n" ]; then
  echo "DEDUP $archive: $orig_n -> $n" >> "${AR_DEDUPE_LOG:-/tmp/ar-dedupe.log}"
fi
# reconroi argv: flags + archive + membros filtrados
set -- "$@"
out=""
skip=0
for a in "$@"; do
  case "$a" in
    -*) out="$out $a"; continue ;;
  esac
  if [ $skip -eq 0 ]; then
    out="$out $a"
    skip=1
  fi
done
# shellcheck disable=SC2086
exec "$REAL_AR" $out $filtered
