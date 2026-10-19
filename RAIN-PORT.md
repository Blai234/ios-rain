# Redmi 10C (`rain`) port status — 2026-10-19

This tree starts from the supplied `MakrSas/ios-topaz` `topaz` branch ZIP
(SHA-256 `ababa8319fb621e1941aac4c5cd306660a3b2ef01c25a1be433f13faffda87f2`).
Topaz itself derives from `dipa-studio/ios-sweet`. Rain now boots XNU and a
minimal test init; full iOS userland remains in bring-up.
The four upstream Topaz patch files 0103–0106 and its README updates were
retrieved from commit `0b78dc55a61ea9c1a693192529a328dedcca31fc` and
checked against GitHub's blob hashes. Rain's patch selection still ends at 0082.

## Live facts read from the connected phone

- Model `220333QNY`, Android codename `rain`, board `bengal`, bootloader unlocked.
- Snapdragon 680 / Khaje; CPU affinity entries `0x0`–`0x3` and `0x100`–`0x103`
  in the archived FDT. Android reports timer interrupt 19.
- `/memory/reg`: `0x40000000+0x3dd00000`, `0x80000000+0x40000000`,
  `0xc0000000+0x80000000` (the last two entries appear in the opposite order).
  Android's live `/proc/iomem` also shows a high RAM reservation at
  `0xf3c00000–0xffbfffff`. The previous XNU window
  `0xb0000000+0x4d000000` **overlapped** this reservation and is retired.
  The revised candidate is `0xb0000000+0x40000000` (1 GiB, ending at
  `0xf0000000`), 60 MiB below the observed reservation. A live preflight
  checks for other overlaps; placement still needs confirmation at XNU boot.
- The highest fixed `/reserved-memory` region found in the FDT is below
  `0x63900000`; that fact alone did not account for Android's high RAM
  allocation.
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
- `tools/check_rain_memory.py --adb PATH_TO_ADB` checks the current Android
  `/proc/iomem` for holes or reservations in the proposed XNU window.
  `tools/validate_rain_payload.py` rejects malformed payload bounds, wrong
  Rain memory and framebuffer properties, and storage unless an explicit
  read-only or volatile UFS mode is selected. Both Rain
  shim builders run the payload preflight before embedding a kernel.
- The Rain tests check identity, storage exclusion, memory reservations,
  payload bounds, boot-image round-trip, and rejected placement mismatches.
- `.github/workflows/xnu.yml` has a `rain` device selection that stops the
  patch series at 0082 plus Rain's `0082-zrain-ufs-cow.patch`. Topaz's 0083–0106 touch, PMIC and display MMIO changes
  remain in the Topaz build only. For Rain, `tools/rewrite_rain_xnu_patch.py`
  rewrites the dependent early-console patches 0010 and 0012 from Sweet's
  `0x9c000000`, 1080×2400, 4320-byte framebuffer to Rain's `0x5c000000`,
  720×1650, 2880-byte layout, and keeps all 21 stage markers within 720 px.
  Both rewritten diffs parse with `git apply --stat`. The Rain XNU build passed
  in GitHub Actions run `39225824047` at commit `c4da78e`. The kernel SHA-256
  is `324d2f5d111a4c110128513ddbfd54dc777aaeb4f42ac49ea8a0f9da851e4cdc`.
  The rewriter copies untouched binary patches byte for byte.

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

After this diagnostic boot, a read-only Android memory audit found the high
reservation described above. The source now uses the smaller 1 GiB Rain
window. The live `/proc/iomem` checker accepted it, 14 Rain tests passed, and
the revised shim rebuilt offline. Neither the revised shim nor an XNU payload
using the new memory window has been booted on the phone. The offline boot
candidate is `shim/out/shim-boot.img` (15,941,632 bytes, SHA-256
`804b06a70f5d83c809fff96bf7a652cbbbcac8ac1285ff140e3f7561d0d9af89`).

## Userspace milestone, 2026-10-19

Mockfs ramdisk boot with a minimal PID 1 (sweet-init.S): the kernel mounted
md0 as BSD root, crossed the user/kernel boundary, and exec'd the init binary.
The init opens `/dev/console`, writes `*** SWEET userspace: init running as
PID 1 ***`, then loops printing heartbeats every 5 seconds. User photo
`IMG_0130.jpeg` confirms: `BSD root: md0, major 1, minor 0`, then
`load_init_program: attempting to load /sbin/launchd`, then the PID 1 message
and multiple alive heartbeats. Syscalls (open, write, getpid, select) all work.

The boot image is `xnu/out-rain-ci/mockfs-shim/shim-boot.img` (21,929,984
bytes). The init binary (16,635 bytes, ad-hoc signed arm64 Mach-O) was compiled
with host LLVM 22 from `tools/sweet-init.S` via `tools/mkinit.py` and used as
`--ramdisk` to `tools/mkpayload.py` (mockfs serves it as `/sbin/launchd`).
The ADT is `research/rain-product.adt` (includes D22AP `/product` node for
iPhone X identity). Command line:
`debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress rd=md0`.
This is a temporary `fastboot boot`; nothing was flashed.

## Read-only UFS root and launchd panic, 2026-10-19

The user's `IMG_0137.jpeg` and `IMG_0138.jpeg` show a later temporary XNU
boot that found `userdata` through the UFS driver in **read-only** mode,
mounted `iOSRoot` as HFS, and attempted to load `/sbin/launchd`. The panic is
`unexpected SIGKILL of launchd (CS_KILLED)` with OS_REASON_EXEC namespace 9,
code `0xe`. The inherited Sweet bring-up encountered this same code when an
iOS binary was rejected by the macOS-configured kernel; it progressed with
`unentitled_ios_sim_launch=1`. The later "home handshake structure not
initialized" line is not yet proven to be the cause of the launchd kill.

The new `xnu/out-rain-ci/ufsroot-platform-shim/shim-boot.img` retains the
same kernel, ADT, and segments as the user's `ufsroot0` payload while adding
that one boot argument. It passed a new explicit read-only UFS preflight:
the ADT host address is `0x04804000`, the root is `ufsroot0`, and neither
`ufsrw` nor `rootrw` is present. Its SHA-256 is
`8ac791ff757705e3120b650343105f0a1fb00f4c8c2af9294ea9671bbc5afd19`.
`fastboot boot` accepted it. The user's `IMG_0139.jpeg` shows `launchd`
running `fsck` and `mount-phase-1`, so it passed the previous platform kill.
`mount_hfs` cannot update `/` on the read-only UFS device (`Read-only file
system`), and `mount` exits status 1; launchd then panics on that failed boot
task. This boot did not flash a phone partition. The origin of the HFS image
already on the phone has not been verified in this session.

The next candidate patch adds `ufscow=1`: physical reads still come from
`userdata`, while a bounded 64 MiB RAM overlay absorbs block writes and
substitutes them on later reads. It refuses physical UFS data-out commands
in this mode and disables the persistent partition log. `rootrw=1` allows
HFS to mount writable against that volatile device. The preflight requires
both arguments and rejects `ufsrw`; 19 Rain tests pass. The patch applies to
the selected 0082 UFS source, but no kernel build or phone boot has yet
validated it. Overlay contents disappear on reset.

## Remaining gates before XNU / iOS boot

1. Reconcile hardcoded 1080×2400 framebuffer and touch values in inherited XNU
   display and HID patches with Rain's 720×1650 panel. The early bootstrap
   console patch now uses Rain geometry, but later `SweetHID` scaling and
   userland display presentation remain inherited. The D22AP `/product`
   device tree has been extracted from Apple's iPhone X 16.7.16 restore image
   into ignored `research/ipsw-x/d22ap.adt`.
2. Build and test the volatile UFS overlay, then work through the next
   userland boot failure. Repeat the live memory preflight before future
   kernel placement changes.
3. Implement and test Rain's Focaltech SPI touch and key services using the
   observed driver, GPIO and PMIC data. The Topaz touch driver and MDP timings
   are device-specific and remain excluded.
4. Audit and test the physical UFS write path with disposable media or instrumentation. The
   Topaz project records LUN0 GPT damage after iOS writes; patch 0088 adds a
   guard and watchdog but does not establish the underlying cause. Keep UFS
   physical device read-only during Rain boot tests; the read-only mount
   observed in the photos does not validate writes. No partition flash was
   performed in this session.

`tools/backup_rain.py` makes read-only local copies of small calibration and
boot partitions in ignored `backup/`. It saved 13 partitions to
`backup/rain-2026-10-19/` (563,347,456 bytes total); a second pass rehashed all
images against `SHA256.json`. These include `persist`, both modem state copies,
`fsg`, `fsc`, both boot and vendor_boot slots, both dtbo slots, and both vbmeta
slots. Keep this directory private: calibration partitions may contain unique
device data. The temporary shim test only rebooted and used `fastboot boot`;
no flash or partition write was performed.
