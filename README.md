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

## Build via Actions (marble)
1. Push nesta branch dispara `build-marble-diwali`.
2. Job `dtb-check` (rápido, ~2min): valida `diwali.dts`/`diwali-idp.dts` com `dtc` e publica `diwali-dtb-test`.
3. Job `full-kernel`: sincroniza kernel+modules do ltdq, sobrepõe `devicetrees/qcom/diwali*` + `Makefile` + `build.config.msm.diwali` e roda `BUILD_CONFIG=build.config.msm.diwali build/build.sh`. Artefato `marble-kernel-out` (Image + dtb/dtbo).
4. Local rápido: `./build.sh` (só monta a árvore, sem compilar).

## Pontas soltas p/ bootar recovery no marble
- [ ] `kernel`: confirmar `ARCH_DIWALI` + drivers `clk-diwali/pinctrl-diwali/interconnect-diwali` (já existe `ARCH_DIWALI` no Kconfig.platforms do ltdq; se faltar driver, cherry-pick do `waipio-kernel-*`).
- [ ] `modules`: mesma branch `lineage-24.0`, `BOARD_VENDOR_RAMDISK_KERNEL_MODULES` do device marble precisa bater com `vendor_dlkm`.
- [ ] `device marble`: `BOARD_KERNEL_PAGESIZE=4096`, `HEADER_VERSION=4`, `BOARD_USES_DTBOIMAGE=true`, `BOARD_PREBUILT_DTBOIMAGE` ou `BOARD_KERNEL_DTBO` -> `diwali-*.dtbo` daqui.
- [ ] Tela/painel marble (`amoled`): `diwali-idp-amoled-overlay.dtbo` é o candidato; se não acender, trocar base para `diwali-*.dtb` + overlay amoled no `recovery.fstab`/cmdline.
- [ ] Primeiro teste: fastboot boot de `vendor_boot`+`boot` com ramdisk de recovery TWRP/Lineage, não flashar.
