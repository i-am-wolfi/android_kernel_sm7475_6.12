#!/bin/bash
# Build marble (diwali/SM7475) sobre base ltdq sm8450-6.12
# Uso local: ./build.sh | No Actions: ver .github/workflows/build.yml
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
KDIR="$ROOT/kernel"
BR=lineage-24.0

[ -d "$KDIR" ] || git clone --depth 1 --branch $BR https://github.com/ltdq/android_kernel_qcom_sm8450-6.12 "$KDIR"
[ -d "$KDIR/vendor/qcom/devicetrees" ] || {
  mkdir -p "$KDIR/vendor/qcom"
  git clone --depth 1 --branch $BR https://github.com/ltdq/android_kernel_qcom_sm8450-devicetrees-6.12 "$KDIR/vendor/qcom/devicetrees-tmp"
  mv "$KDIR/vendor/qcom/devicetrees-tmp" "$KDIR/vendor/qcom/devicetrees"
}
# sobrepõe nossos diwali + Makefile no checkout do kernel
cp -v "$ROOT/devicetrees/qcom/diwali"* "$ROOT/devicetrees/qcom/diwalip"* "$KDIR/vendor/qcom/devicetrees/qcom/" 2>/dev/null || cp -v "$ROOT"/devicetrees/qcom/diwali* "$KDIR/vendor/qcom/devicetrees/qcom/"
cp -v "$ROOT/devicetrees/qcom/Makefile" "$KDIR/vendor/qcom/devicetrees/qcom/Makefile"
cp -v "$ROOT/build.config.msm.diwali" "$KDIR/build.config.msm.diwali"

[ -d "$KDIR/../kernel-modules" ] || git clone --depth 1 --branch $BR https://github.com/ltdq/android_kernel_qcom_sm8450-modules-6.12 "$ROOT/kernel-modules"

echo "=== arvore pronta. Para compilar DTBs (validacao rapida):"
echo "  cd kernel && BUILD_CONFIG=../build.config.msm.diwali build/build.sh --config=fast  # ou kleaf"
echo "=== full build GKI+QCOM (pesado, ~30GB RAM/100GB disco no Actions):"
echo "  cd kernel && BUILD_CONFIG=build.config.msm.diwali build/build.sh"
