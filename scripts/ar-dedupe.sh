#!/bin/sh
# ar-dedupe.sh: wrapper do llvm-ar que remove membros duplicados da mesma
# invocacao (mesmo .o listado 2x por obj-y duplo apos merge de Makefiles).
# Mesmo path 2x == mesmo arquivo == seguro incluir uma vez so.
# So atua em criacao/atualizacao (c/r/q); resto passa direto.
# Loga reducoes em $AR_DEDUPE_LOG (p/ auditoria posterior).
# Uso: make AR="/path/ar-dedupe.sh"
REAL_AR="llvm-ar"

op="$1"
case "$op" in
  *c*|*r*|*q*)
    ;;
  *)
    exec "$REAL_AR" "$@"
    ;;
esac

flags=""
archive=""
members=""
for a in "$@"; do
  case "$a" in
    -*) flags="$flags $a"; continue ;;
    @*) exec "$REAL_AR" "$@" ;;  # response file: nao mexe
  esac
  case "$a" in
    *.*|*/*) ;;
    *) flags="$flags $a"; continue ;;  # flag colada sem '-' (rcsD, cDPrST)
  esac
  if [ -z "$archive" ]; then
    archive="$a"
  else
    members="$members $a"
  fi
done
[ -n "$archive" ] || exec "$REAL_AR" "$@"

seen=""
filtered=""
n=0
orig_n=0
for m in $members; do
  orig_n=$((orig_n + 1))
  # shellcheck disable=SC2001
  key=$(printf '%s' "$m" | sed 's|^\./||')
  case " $seen " in
    *" $key "*) continue ;;
  esac
  seen="$seen $key"
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
# shellcheck disable=SC2086
exec "$REAL_AR" $flags "$archive" $filtered
