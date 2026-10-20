# Redmi 10C (`rain`) port status — 2026-10-20

## Display geometry fix: the canvas the userland reads — 2026-10-20

The Rain device tree gave the userland a `720x1650` canvas, but the kernel
presents the iPhone X size (`1125x2436`) to it. A canvas that differs from
the size `IOMobileFramebuffer` reports makes backboardd look for a hardware
scaler: on Rain it fails on `AppleM2ScalerCSCDriver` on every boot, and no
frame is ever swapped to the panel. The upstream topaz tree documents the
same effect ("a 1125x2436 canvas with `sweetfb_native=1` makes backboardd ask
for a hardware scaler that does not exist").

Fixed in this session:

- `tools/mkadt.py` presents `1125x2436` (the panel size only with `--native`).
  Topaz keeps its previous values.
- `tools/validate_rain_payload.py` refuses a payload whose canvas differs from
  the presented size.
- `xnu/patches/0082-zrain-display-geometry.patch` (Rain only) adds
  `sweetfb_scale=1`, which resamples the canvas into the `720x1650` panel
  instead of showing its centre crop, and takes the digitizer's panel size
  from the device tree instead of the sweet `1080x2400` constants.

Not built and not booted yet: see `NOTES.md`.

The verified Rain nullfilter image was temporarily booted on 2026-10-20:
FASTBOOT product `rain`; send OKAY 0.472 s, boot OKAY 0.388 s. `IMG_0159.jpeg`
shows its backboardd scaler message still flooding the console. A second
temporary image changed only `sweetnull` to `SpringBoard`, preserved the
volatile UFS overlay, and booted with send/boot OKAY. `IMG_0160.jpeg` shows
periodic SpringBoard and backboardd samples and AKS activity without that
flood. No display swap is visible. See `NOTES.md` for both candidate identities,
verification, and the prior battery interruption.

## Latest stall and controlled migration test — 2026-10-20

The gated migration kernel built successfully in macOS Actions run
`39378328083` at `cab7a2e`. Its artifact and internal kernel SHA-256 were
verified. The resulting boot-v3 image passed volatile-UFS preflight and
round-trip packaging, and the connected product reported `rain` before a
temporary `fastboot boot`. Its boot command line adds `rainseedmigration=1`
to the previous 512 MiB COW/one-CPU configuration; no physical write flag is
present. In `IMG_0156.jpeg`, mediaserverd creates a surface while further
services start. In `IMG_0157.jpeg`, COW reports 64 MiB allocated and more
services start. The user says text is still scrolling. No graphical handoff
has been observed, and the one-time seed result is not visible in these
photos. Keep observing this boot before drawing a conclusion.
`IMG_0158.jpeg` later shows 128 MiB COW allocated and live sampler stacks for
SpringBoard and backboardd, with no swap. A Rain-only gated console filter,
`0082-zrain-nullfilter.patch`, is prepared for a later diagnostic boot if
needed; it silences only the known repeated scaler lookup line from
backboardd while preserving other output. Its first CI attempt
(`39381949629`) failed in Build; the kernel artifact was absent and the job
log endpoint failed, so `strstr` was replaced with the kernel's `strnstr` and
the workflow now uploads a build-log artifact. The corrected build passed in
Actions run `39383209117`. The verified temporary image at
`xnu/out-rain-ci/rain-nullfilter-shim/shim-boot.img` has SHA-256
`5fde220c16836b7797daff18931a8d4f3f41f0d57892e4d454fb666220ba59ce`;
it passed volatile-UFS preflight and boot-v3 round trip. It has **not** been
booted. The phone ran out of battery during the seed test; its volatile
overlay disappeared on power loss.

The 512 MiB volatile overlay boot passed the earlier 64 MiB limit.
`IMG_0154.jpeg` shows 192 MiB allocated and additional daemons starting.
`IMG_0155.jpeg` shows service startup continuing, then a static console for
over 30 minutes with no panic or framebuffer swap. The cause is not yet
established.

The saved HFS catalog has the mobile Preferences directory but no
`com.apple.migration.plist` there. A same-named file under
`/System/Library/Preferences/Logging/Subsystems` is unrelated. The root
reports ProductBuildVersion `20H392`; the Rain ADT has the UUID inputs and
display identity. Sweet reached its first graphical setup after seeding
`LastSystemVersion=20H392` in the mobile preference, so migration is a
specific hypothesis to test.

Rain-only `0082-zrain-migration-seed.patch` is a boot-argument-gated test:
with `rainseedmigration=1 ufscow=1` and no `ufsrw`, it creates the mobile
preference in RAM overlay before launchd, writes the build version, and
reports each result. It does nothing without the argument and refuses a
physical-write boot. It applies cleanly to the successful Rain buildtree;
macOS build and phone test remain pending.

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

- `xnu/patches/0082-zrain-display-geometry.patch` (Rain only): the canvas
  the userland reads matches the size the kernel presents, `sweetfb_scale=1`
  resamples the canvas into the panel, and the digitizer takes its panel
  size from the device tree. `tools/mkadt.py` and
  `tools/validate_rain_payload.py` enforce the canvas invariant.
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

`IMG_0151.jpeg` from a one-CPU diagnostic boot shows both `backboardd` and
`SpringBoard` alive in the periodic kernel thread sampler, plus active
`com.apple.datamigrator` and `thermalmonitord`. The console did not disappear
with `sweetfb_noconsole=1`, so the first AppleCLCD swap had not occurred.
`IMG_0152.jpeg` then shows the actual current loop: the volatile UFS COW
overlay repeatedly reports **`64 MiB limit reached`**. Daemon writes are
being refused. This is a confirmed capacity stop for this boot; it does not
establish the cause of the earlier four-CPU HFS error loop. No physical UFS
write was enabled.

The 512 MiB COW kernel from successful Actions run `39299890390` has now
been packaged with exactly the same one-CPU, quiet-output and framebuffer
arguments. The prepared temporary image is
`xnu/out-rain-ci/rain-cow-512-cpu1-graphics-shim/shim-boot.img` (21,929,984
bytes, SHA-256
`5f0aa35ad0bae9e6f535068bf259e533a237594855de5f94a7c0de3e18706f2f`).
Its embedded kernel digest matches the Actions manifest, and its volatile-UFS
preflight and boot-v3 packaging passed. Verified FASTBOOT product `rain`, then
temporary `fastboot boot` returned send OKAY 0.456 s and boot OKAY 0.343 s.
The screen outcome is pending; no partition was flashed.

`IMG_0145.jpeg` is a one-variable A/B test of the 64 MiB COW boot:
`cpus=4` was changed to `cpus=1`, with the same kernel, ADT, root, and other
arguments. It passed the HFS B-tree error loop seen in `IMG_0144.jpeg` and
reached `backboardd`. This points to CPU concurrency or timing as a factor;
it does not identify the fault. `backboardd` repeatedly prints
`IOServiceMatchingFailed for: AppleM2ScalerCSCDriver`. The `|backboardd|`
prefix comes from the inherited `/dev/null` tee and is not subject to the
IOKit tracer's 400-line limit. The photo does not prove that this missing
service prevents the GUI; a later screen observation is pending.

The 512 MiB COW revision built successfully in Actions run
[`39299890390`](https://github.com/Blai234/ios-rain/actions/runs/39299890390)
at commit `c082ce4`. The verified kernel SHA-256 is
`f4d05445d1c1be0241d51e40db0e6339186df24f9549b4acfd6bb28dbc15d333`.
It has not been device-tested. A temporary diagnostic image using the proven
64 MiB kernel, `cpus=1`, and `sweetnull=SpringBoard` is prepared at
`xnu/out-rain-ci/rain-cow-cpu1-quiet-shim/shim-boot.img` (SHA-256
`77f5ca12f850dac8ec6a5b7e58844866fcc6dbc5e81fcb15622aae8788997673`).
That argument suppresses only `backboardd`'s `/dev/null` echo so other
console diagnostics can be observed. Its volatile-UFS preflight and boot-v3
packaging passed. After verifying the bootloader reports product `rain`, a
temporary `fastboot boot` returned send OKAY 0.462 s and boot OKAY 0.380 s.
The screen result is pending.

`IMG_0144.jpeg` is the second temporary COW boot's result. It passed the
`launchd_cache_loader` AMFI stop and launched further services, including
`bluetoothuserd`, then printed repeated HFS B-tree `offset #0 invalid
(0x0000)` errors for catalog (fileID 4) and attributes (fileID 8), followed
by `hfs_mark_inconsistent`. The user confirmed this loop persists. This boot
had `ufscow=1`, so its disk writes were volatile.

Read-only recovery analysis found `/dev/block/sda16` is Rain's `userdata`
(109,844,443,136 bytes, starts at UFS 4 KiB LBA `0x2b4c28`). The phone HFS
header, catalog and attributes header nodes are structurally valid. All
19,694 allocated catalog nodes have valid descriptors and record offsets;
against the source sparse HFS image, only catalog nodes 0, 1 and 19693
changed. The attributes tree has only node 0 allocated. On-disk damage does
not explain the visible zero-node errors by itself. This does not prove the
whole filesystem is sound; the later `cpus=1` A/B test points more strongly
to an SMP or timing issue than COW capacity alone. Samples are outside Git at
`C:/Users/Blai/Downloads/rain-hfs-diagnostic/`.

The revised Rain COW patch raises its cap to 512 MiB, reports each 64 MiB
high-water mark, and returns all-overlaid reads from RAM without a physical
UFS read. It still blocks physical UFS writes. Its macOS build passed; its
effect on the phone has not been assessed.

`IMG_0143.jpeg` confirms the first temporary Rain COW boot passed root mount
and several launchd boot tasks. It stops at `launchd_cache_loader[22]`:
`Unable to find AMFI`, exit namespace 7 subcode `0x1`, followed by panic.
The inherited Sweet notes record this exact gate and
`launchd_unsecure_cache=1` as its development workaround. The prepared
`xnu/out-rain-ci/rain-cow-unsecure-cache-shim/shim-boot.img` appends only that
argument to the preceding payload. SHA-256:
`c4c429a2b8020dd121b6c96d56e9fc057b90d49b0ad5ddb09f7f3b35ed4e707c`.
The command line retains `unentitled_ios_sim_launch=1 ufscow=1 rootrw=1`
and omits `ufsrw`; preflight and boot-v3 packager passed. Its first phone
test awaits FASTBOOT.

The user's later `IMG_0142.jpeg` shows an independent physical read-write
UFS boot (`SWEET UFS` says read-write, and persistent `SWEET LOG` starts).
It panics again on `launchd` `CS_KILLED`, namespace 9 code `0xe`. The exact
boot image and command line were not supplied, so the missing platform boot
argument is a likely explanation based on the earlier A/B test, not a
verified property of this image. Do not repeat physical-write boots while
the inherited Topaz GPT damage risk remains unresolved.

The Rain COW kernel build actually succeeded in Actions run `39281892841`
at commit `3212edb`. Artifact ZIP digest is
`38f127d532856d18ede50b861cd2f39eca61a79e6953578d1b7ad3666e376f7e`;
kernel digest matches its Actions manifest:
`edda2c82c972ef4c0f50ca06a505d0d3d05416feae7ac4f36995ae8db2a9f9a1`.
The prepared temporary COW image
`xnu/out-rain-ci/rain-cow-platform-shim/shim-boot.img` is 21,929,984 bytes,
SHA-256 `0015d8ba34083b637171607f1185f6dcde0eb41f52a80191bd56d7f189b4802f`.
Its cmdline includes `unentitled_ios_sim_launch=1 ufscow=1 rootrw=1`, with no
`ufsrw`. The image passed the Rain volatile-UFS preflight and host boot-image
round-trip. It is awaiting a temporary `fastboot boot` test.

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
the selected 0082 UFS source. The kernel build passed, but its behavior on
the phone remains untested. Commit `3212edb` was pushed; Actions run
`39281892841` succeeded, and the next temporary boot image is prepared above.
Overlay contents disappear on reset.

## Remaining gates before XNU / iOS boot

1. **Build and boot the display geometry fix.** The canvas now matches the
   size the kernel presents, and `sweetfb_scale=1` can resample the canvas
   into Rain's `720x1650` panel. A temporary boot has to show whether the
   GUI comes up, first without the argument (centre crop) and then with it.
   The inherited XNU display and HID patches still carry sweet's geometry
   elsewhere; the digitizer is now device-tree driven.
2. Test the built volatile UFS overlay, then work through the next
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
