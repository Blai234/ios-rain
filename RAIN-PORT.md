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
  size is 720×1650. A temporary shim boot drew stable text and colors through
  this region at a 2880-byte row stride with 32-bit pixels; the exact ABL
  scanout format was not independently read from bootloader registers.
- GICD `0x0f200000`, GICR `0x0f300000`, UFS host `0x04804000`. These match
  Topaz's SoC addresses, but matching addresses do not validate the drivers.
- The active Android panel is `dsi_panel_c3q_43_03_0b_fhdp_video_display`
  (FT8006S video mode, 720×1650 at 60 Hz). Android loads `fts_ts` over SPI
  (`spi0.0`, Focaltech driver V3.2.2, controller ID `0x8642`), with touch
  coordinates 0–719 and 0–1649. Its disabled I²C touch alternatives are not
  the active controller. The PMIC is PM6125; the volume-up key reports Linux
  code 115. Selected public DT properties are in ignored `research/`.
- Backed-up `boot_a` has Android boot header v3, 4096-byte pages, a gzip ARM64
  kernel with text offset `0x80000` and flags `0xa`. `vendor_boot_a` is v3.

## Source changes

- `tools/mkadt.py --rain` emits Rain identity, a 720×1650 framebuffer and
  canvas, the low RAM window, and no `sweet-ufs` node. It rejects `--highmem`.
- `TARGET=rain shim/build.sh` selects Rain console dimensions, stock ARM64
  image placement, omits Topaz's unverified CPU frequency write, and excludes
  the UFS probe from the executable. `tools/build_rain_shim.py` builds the same
  diagnostic shim with host LLVM on Windows. `tools/pack_rain_boot.py` wraps it
  with the backed-up stock boot header and ramdisk in gzip boot-v3 form.
- `tests/test_rain_adt.py` and `tests/test_rain_boot.py` check Rain identity,
  storage exclusion, boot-image round-trip, and rejected placement mismatches.
- `.github/workflows/xnu.yml` has a `rain` device selection that stops the
  patch series at 0082. Topaz's 0083–0106 touch, PMIC and display MMIO changes
  remain in the Topaz build only. For Rain, `tools/rewrite_rain_xnu_patch.py`
  rewrites the dependent early-console patches 0010 and 0012 from Sweet's
  `0x9c000000`, 1080×2400, 4320-byte framebuffer to Rain's `0x5c000000`,
  720×1650, 2880-byte layout, and keeps all 21 stage markers within 720 px.
  Both rewritten diffs parse with `git apply --stat`; compilation is pending.

## Temporary boot result, 2026-10-19

Host LLVM 22 built the 151,552-byte shim, packaged into a 15,941,632-byte
boot-v3 image. Seven source tests passed, and the packager independently
round-tripped the kernel and verified the stock ramdisk unchanged. A single
`fastboot boot` returned OKAY for send and boot; **nothing was flashed**. The
tested image's SHA-256 was
`5a76916d88afed64243b2adc2a835d49ffebb743961181a62c4938165ac0aabf`.
The user's `IMG_0125.jpeg` and `IMG_0126.jpeg` show the red diagnostic console:
Silver had no 16K translation granule, Gold ran the shim, the virtual timer
reported `0x1e` (30) IRQs, SGI1 reported `0x0a` (10) IRQs, and the loader
reported `no SWEETXNU payload` as expected. This establishes shim execution,
basic framebuffer output, CPU handoff, and interrupt delivery on this phone.
The first image's text clipped at the right edge; the source now uses a smaller
Rain console scale and a rebuilt local image, which has not itself been booted.
The automatic reset was not observed: after more than the programmed delay,
the red screen remained and neither ADB nor fastboot enumerated. A 15–20 second
Power-button hold returned the phone to Android; ADB confirmed boot completed
on slot A. The reset code now shows a manual recovery hint if PSCI/PSHOLD
return, but that revision has not been device-tested.

## Remaining gates before XNU / iOS boot

1. Reconcile hardcoded 1080×2400 framebuffer and touch values in inherited XNU
   display and HID patches with Rain's 720×1650 panel. The early bootstrap
   console patch now uses Rain geometry, but later `SweetHID` scaling and
   userland display presentation remain inherited. The copied tree has no XNU
   binary or iPhone X `/product` device tree. Rain's macOS CI has not been run.
2. Validate an XNU kernel build on a macOS runner, then create a matching
   payload for the shim. Check memory placement, early console and the panel
   path before connecting storage or trying iOS userland.
3. Implement and test Rain's Focaltech SPI touch and key services using the
   observed driver, GPIO and PMIC data. The Topaz touch driver and MDP timings
   are device-specific and remain excluded.
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
device data. The temporary shim test only rebooted and used `fastboot boot`;
no flash or partition write was performed.
