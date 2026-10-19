# Redmi 10C (`rain`) port status — 2026-10-19

This tree starts from the supplied `MakrSas/ios-topaz` `topaz` branch ZIP
(SHA-256 `ababa8319fb621e1941aac4c5cd306660a3b2ef01c25a1be433f13faffda87f2`).
Topaz itself derives from `dipa-studio/ios-sweet`. The Rain changes are an **early
hardware configuration**, not a working XNU or iOS build.
The four upstream Topaz patch files 0103–0106 and its README updates were
retrieved from commit `0b78dc55a61ea9c1a693192529a328dedcca31fc` and
checked against GitHub's blob hashes. Rain's patch selection still ends at 0082.

## Live facts read from the connected phone

- Model `220333QNY`, Android codename `rain`, board `bengal`, bootloader unlocked.
- Snapdragon 680 / Khaje; CPU affinity entries `0x0`–`0x3` and `0x100`–`0x103`
  in the archived FDT. Android reports timer interrupt 19.
- `/memory/reg`: `0x40000000+0x3dd00000`, `0x80000000+0x40000000`,
  `0xc0000000+0x80000000` (the last two entries appear in the opposite order).
  The selected XNU window `0xb0000000+0x4d000000` lies in these banks.
- The highest fixed `/reserved-memory` region observed is below `0x63900000`.
  `cont_splash_region` is `0x5c000000+0x00f00000`; Android's physical display
  size is 720×1650. The ABL framebuffer stride and pixel format still need a
  direct boot-time measurement.
- GICD `0x0f200000`, GICR `0x0f300000`, UFS host `0x04804000`. These match
  Topaz's SoC addresses, but matching addresses do not validate the drivers.

## Source changes

- `tools/mkadt.py --rain` emits Rain identity, a 720×1650 framebuffer and
  canvas, the low RAM window, and no `sweet-ufs` node. It rejects `--highmem`.
- `TARGET=rain shim/build.sh` selects Rain console dimensions, omits Topaz's
  unverified CPU frequency write, and disables the no-payload UFS probe.
- `tests/test_rain_adt.py` checks the Rain invariants and Topaz defaults.
- `.github/workflows/xnu.yml` has a `rain` device selection that stops the
  patch series at 0082. Topaz's 0083–0102 touch, PMIC and display MMIO changes
  remain in the Topaz build only.

## Remaining gates before a device boot

1. Confirm the ABL framebuffer stride, format, and whether a boot image v4 is
   accepted on Rain. Reconcile the hardcoded 1080×2400 values in the inherited
   XNU framebuffer and touch patches. The present shim build has not been
   compiled or sent to the phone.
2. Obtain a build environment with an AArch64 cross compiler, `mkbootimg.py`,
   and a macOS XNU build runner. The copied source has no XNU binary or iPhone
   X `/product` device tree. Build and inspect a storage-free diagnostic image
   before trying any iOS root. The `rain` CI selection has not been run.
3. Identify Rain's touch controller, PMIC key wiring, panel scanout, and exact
   partition geometry from this device. Topaz FT5452, PM6125 and MDP settings
   cannot be assumed to apply.
4. Audit and test the UFS driver with disposable media or instrumentation. The
   Topaz project records LUN0 GPT damage after iOS writes; patch 0088 adds a
   guard and watchdog but does not establish the underlying cause. Keep Rain's
   storage node absent until this is resolved and all phone partitions are
   backed up. No `userdata` flash is part of this baseline.

`tools/backup_rain.py` makes read-only local copies of small calibration and
boot partitions in ignored `backup/`. It saved 13 partitions to
`backup/rain-2026-10-19/` (563,347,456 bytes total); a second pass rehashed all
images against `SHA256.json`. These include `persist`, both modem state copies,
`fsg`, `fsc`, both boot and vendor_boot slots, both dtbo slots, and both vbmeta
slots. Keep this directory private: calibration partitions may contain unique
device data. No reboot, fastboot boot, flash, or partition write was performed.
