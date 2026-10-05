# android_kernel_sm7475_6.12 (marble / diwali) — base waipio 6.12

Base: ltdq/android_kernel_qcom_sm8450-devicetrees-6.12 (lineage-24.0) + diwali de waipio-kernel-devicetree/kernel-devicetree.

SoC: SM7475 (diwali) — Poco F5 / Redmi Note 12 Turbo (marble). Derivado de waipio (SM8450).

O que foi feito:
- importados `qcom/diwali*` + `qcom/diwalip*`
- overlays renomeados `.dts` -> `.dtso` (padrão 6.12)
- bloco `DIWALI_BASE_DTB` + `CONFIG_ARCH_DIWALI` no `qcom/Makefile`

Falta (kernel + modules + device):
- `CONFIG_ARCH_DIWALI=y` no defconfig, drivers clk/pinctrl/gdsc-diwali no kernel 6.12
- `android_kernel_qcom_sm8450-6.12` + `-modules-6.12` com mesmo patch
- device `marble` apontando DTB diwali + blobs

Ref: waipio (8450) / cape (8475) / diwali (7475).
