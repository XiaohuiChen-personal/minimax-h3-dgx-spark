# Spark prerequisite checks

**When (UTC):** Sun Aug 23 10:26:05 PM UTC 2026 (`date -u`, Step 1)
**Host:** spark-2a60
**BASE_IMAGE:** `nvcr.io/nvidia/pytorch:25.12-py3`
**Result:** all required checks **PASS**. Later tasks may start (`uname -m` is `aarch64`; GPU is NVIDIA GB10 / compute 12.1).

## Gate summary

| Check | Expected | Observed | Result |
|---|---|---|---|
| `uname -m` | `aarch64` | `aarch64` | **PASS** |
| GPU / compute | GB10 / 12.1 | `NVIDIA GB10`, compute `12.1` | **PASS** |
| Driver / CUDA | 580.x / CUDA 13 | Driver `580.159.03`, CUDA `13.0` | **PASS** |
| System Python torch | CPU or missing (known trap) | `2.10.0+cpu` `cuda False` | **PASS** |
| Docker GPU | talks to a GPU runtime | NVIDIA Container Toolkit `1.19.1`; CDI `nvidia.com/gpu=all`; `DefaultRuntime=runc`; `--gpus all` works | **PASS** |
| NIC link | 8000Mb/s or 10000Mb/s | **10000Mb/s** Full, iface `enP7s7`, driver `r8127` | **PASS** |
| GPU-in-container | `True` + GB10-like name | `2.10.0a0+b4e4ee81d3.nv25.12 True NVIDIA GB10` | **PASS** |
| Disk headroom | ~60 GiB weights + ~30 GiB images | `$HOME` and `/var/lib/docker`: **2.6T** avail (same nvme) | **PASS** |

## BASE_IMAGE

```
nvcr.io/nvidia/pytorch:25.12-py3
```

**Choice and rationale.** Task 1 requires this tag first. It exists and is **not** x86-only: `docker manifest inspect` lists `linux/amd64` and `linux/arm64` (arm64 digest `sha256:a086b7d17665c18526fd28f8d65fde91b92475289262bf419ca4b55e244709eb`). Pulled with `--platform linux/arm64`. `docker image inspect`: `Architecture=arm64`, `Os=linux`, `Size=19727354200`, `Id=sha256:edda8a492f5b602234cde15ddcc8f1f31562dcbe4eaabfb9433ece2dd21f9780`. NVIDIA PyTorch 25.12 release notes: CUDA **13.1.0**. In-container: `torch.version.cuda` `13.1`, capability `(12, 1)`, `torch.cuda.is_available()` `True` on `NVIDIA GB10`.

Did **not** switch to a newer catalog tag (NGC page listed a later `26.05-py3`). The fallback (“list tags and pick the newest linux/arm64 / CUDA 13”) applies only if `25.12-py3` is missing or x86-only.

## Disk headroom

Need about **60 GiB** for weights + **30 GiB** for images (~90 GiB). After the NGC pull, both `$HOME` and `/var/lib/docker` report **2.6T** available on `/dev/nvme0n1p2` (3.7T, 28% used). Headroom is far above the floor.

## GPU-in-container

`torch.cuda.is_available()` printed **True**. Device name: **NVIDIA GB10**. CUDA runtime 13.1. Compute capability `(12, 1)`.

The NGC entrypoint enabled CUDA Forward Compatibility (`Using CUDA 13.1 driver version 590.44.01 with kernel driver version 580.159.03`). Smoke still returned True / GB10.

## Notes

- Docker’s named runtimes are `runc` and `io.containerd.runc.v2`. There is no `DefaultRuntime=nvidia`. GPU access on this box is **NVIDIA Container Toolkit 1.19.1 + CDI** (`nvidia.com/gpu=0`, `nvidia.com/gpu=all`) plus `docker run --gpus all`. Marked PASS because the in-container smoke printed `True` / `NVIDIA GB10`.
- First pull of `25.12-py3` reused some layers already present from local `nvcr.io/nvidia/pytorch:25.11-py3`. Wall-clock was **181.82 s**, so this is **not** a cache-hit (`seconds < 0.01`). Speed-log bytes are `docker image inspect` `.Size` (uncompressed).
- Did not download H3 weights. Did not add `H3_LICENSE_ACK`. Did not pull x86_64 as the product image.

---

## Step 1 — Collect identity (verbatim)

### `date -u`

```
Sun Aug 23 10:26:05 PM UTC 2026
```

### `uname -a`

```
Linux spark-2a60 6.17.0-1021-nvidia #21-Ubuntu SMP PREEMPT_DYNAMIC Wed May 27 19:14:05 UTC 2026 aarch64 aarch64 aarch64 GNU/Linux
```

### `uname -m`

```
aarch64
```

### `nvidia-smi`

```
Sun Aug 23 17:26:05 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 580.159.03             Driver Version: 580.159.03     CUDA Version: 13.0     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA GB10                    On  |   0000000F:01:00.0  On |                  N/A |
| N/A   42C    P0              8W /  N/A  | Not Supported          |      6%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A         2011225      G   /usr/share/cursor/cursor                168MiB |
|    0   N/A  N/A         3345981      G   /usr/lib/xorg/Xorg                      559MiB |
|    0   N/A  N/A         3346134      G   /usr/bin/gnome-shell                    349MiB |
|    0   N/A  N/A         3347112      G   ...rack-uuid=3190708988185955192        197MiB |
+-----------------------------------------------------------------------------------------+
```

### compute capability (gate: GB10 / 12.1)

`nvidia-smi` table names the GPU but does not print `12.1`. Extra query used for the written gate:

```
$ nvidia-smi --query-gpu=name,compute_cap,driver_version --format=csv
name, compute_cap, driver_version
NVIDIA GB10, 12.1, 580.159.03
```

### system Python torch (known CPU trap)

```
$ python3 -c "import torch; print('sys-python-torch', getattr(torch, '__version__', None), 'cuda', torch.cuda.is_available())" || echo "sys-python-no-torch"
sys-python-torch 2.10.0+cpu cuda False
```

### `docker version --format '{{.Server.Version}}'`

```
29.2.1
```

### `docker info --format 'Runtimes={{.Runtimes}} DefaultRuntime={{.DefaultRuntime}}'`

```
Runtimes=map[io.containerd.runc.v2:{{runc []  map[]} map[org.opencontainers.runtime-spec.features:{"ociVersionMin":"1.0.0","ociVersionMax":"1.2.1","hooks":["prestart","createRuntime","createContainer","startContainer","poststart","poststop"],"mountOptions":["async","atime","bind","defaults","dev","diratime","dirsync","exec","iversion","lazytime","loud","mand","noatime","nodev","nodiratime","noexec","noiversion","nolazytime","nomand","norelatime","nostrictatime","nosuid","nosymfollow","private","ratime","rbind","rdev","rdiratime","relatime","remount","rexec","rnoatime","rnodev","rnodiratime","rnoexec","rnorelatime","rnostrictatime","rnosuid","rnosymfollow","ro","rprivate","rrelatime","rro","rrw","rshared","rslave","rstrictatime","rsuid","rsymfollow","runbindable","rw","shared","silent","slave","strictatime","suid","symfollow","sync","tmpcopyup","unbindable"],"linux":{"namespaces":["cgroup","ipc","mount","network","pid","time","user","uts"],"capabilities":["CAP_CHOWN","CAP_DAC_OVERRIDE","CAP_DAC_READ_SEARCH","CAP_FOWNER","CAP_FSETID","CAP_KILL","CAP_SETGID","CAP_SETUID","CAP_SETPCAP","CAP_LINUX_IMMUTABLE","CAP_NET_BIND_SERVICE","CAP_NET_BROADCAST","CAP_NET_ADMIN","CAP_NET_RAW","CAP_IPC_LOCK","CAP_IPC_OWNER","CAP_SYS_MODULE","CAP_SYS_RAWIO","CAP_SYS_CHROOT","CAP_SYS_PTRACE","CAP_SYS_PACCT","CAP_SYS_ADMIN","CAP_SYS_BOOT","CAP_SYS_NICE","CAP_SYS_RESOURCE","CAP_SYS_TIME","CAP_SYS_TTY_CONFIG","CAP_MKNOD","CAP_LEASE","CAP_AUDIT_WRITE","CAP_AUDIT_CONTROL","CAP_SETFCAP","CAP_MAC_OVERRIDE","CAP_MAC_ADMIN","CAP_SYSLOG","CAP_WAKE_ALARM","CAP_BLOCK_SUSPEND","CAP_AUDIT_READ","CAP_PERFMON","CAP_BPF","CAP_CHECKPOINT_RESTORE"],"cgroup":{"v1":true,"v2":true,"systemd":true,"systemdUser":true,"rdma":true},"seccomp":{"enabled":true,"actions":["SCMP_ACT_ALLOW","SCMP_ACT_ERRNO","SCMP_ACT_KILL","SCMP_ACT_KILL_PROCESS","SCMP_ACT_KILL_THREAD","SCMP_ACT_LOG","SCMP_ACT_NOTIFY","SCMP_ACT_TRACE","SCMP_ACT_TRAP"],"operators":["SCMP_CMP_EQ","SCMP_CMP_GE","SCMP_CMP_GT","SCMP_CMP_LE","SCMP_CMP_LT","SCMP_CMP_MASKED_EQ","SCMP_CMP_NE"],"archs":["SCMP_ARCH_AARCH64","SCMP_ARCH_ARM","SCMP_ARCH_MIPS","SCMP_ARCH_MIPS64","SCMP_ARCH_MIPS64N32","SCMP_ARCH_MIPSEL","SCMP_ARCH_MIPSEL64","SCMP_ARCH_MIPSEL64N32","SCMP_ARCH_PPC","SCMP_ARCH_PPC64","SCMP_ARCH_PPC64LE","SCMP_ARCH_RISCV64","SCMP_ARCH_S390","SCMP_ARCH_S390X","SCMP_ARCH_X86","SCMP_ARCH_X86_64"],"knownFlags":["SECCOMP_FILTER_FLAG_TSYNC","SECCOMP_FILTER_FLAG_SPEC_ALLOW","SECCOMP_FILTER_FLAG_LOG"],"supportedFlags":["SECCOMP_FILTER_FLAG_TSYNC","SECCOMP_FILTER_FLAG_SPEC_ALLOW","SECCOMP_FILTER_FLAG_LOG"]},"apparmor":{"enabled":true},"selinux":{"enabled":true},"intelRdt":{"enabled":true},"mountExtensions":{"idmap":{"enabled":true}}},"annotations":{"io.github.seccomp.libseccomp.version":"2.5.5","org.opencontainers.runc.checkpoint.enabled":"true","org.opencontainers.runc.commit":"v1.3.4-0-gd6d73eb8","org.opencontainers.runc.version":"1.3.4\n"},"potentiallyUnsafeConfigAnnotations":["bundle","org.systemd.property.","org.criu.config"]}]} runc:{{runc []  map[]} map[org.opencontainers.runtime-spec.features:{"ociVersionMin":"1.0.0","ociVersionMax":"1.2.1","hooks":["prestart","createRuntime","createContainer","startContainer","poststart","poststop"],"mountOptions":["async","atime","bind","defaults","dev","diratime","dirsync","exec","iversion","lazytime","loud","mand","noatime","nodev","nodiratime","noexec","noiversion","nolazytime","nomand","norelatime","nostrictatime","nosuid","nosymfollow","private","ratime","rbind","rdev","rdiratime","relatime","remount","rexec","rnoatime","rnodev","rnodiratime","rnoexec","rnorelatime","rnostrictatime","rnosuid","rnosymfollow","ro","rprivate","rrelatime","rro","rrw","rshared","rslave","rstrictatime","rsuid","rsymfollow","runbindable","rw","shared","silent","slave","strictatime","suid","symfollow","sync","tmpcopyup","unbindable"],"linux":{"namespaces":["cgroup","ipc","mount","network","pid","time","user","uts"],"capabilities":["CAP_CHOWN","CAP_DAC_OVERRIDE","CAP_DAC_READ_SEARCH","CAP_FOWNER","CAP_FSETID","CAP_KILL","CAP_SETGID","CAP_SETUID","CAP_SETPCAP","CAP_LINUX_IMMUTABLE","CAP_NET_BIND_SERVICE","CAP_NET_BROADCAST","CAP_NET_ADMIN","CAP_NET_RAW","CAP_IPC_LOCK","CAP_IPC_OWNER","CAP_SYS_MODULE","CAP_SYS_RAWIO","CAP_SYS_CHROOT","CAP_SYS_PTRACE","CAP_SYS_PACCT","CAP_SYS_ADMIN","CAP_SYS_BOOT","CAP_SYS_NICE","CAP_SYS_RESOURCE","CAP_SYS_TIME","CAP_SYS_TTY_CONFIG","CAP_MKNOD","CAP_LEASE","CAP_AUDIT_WRITE","CAP_AUDIT_CONTROL","CAP_SETFCAP","CAP_MAC_OVERRIDE","CAP_MAC_ADMIN","CAP_SYSLOG","CAP_WAKE_ALARM","CAP_BLOCK_SUSPEND","CAP_AUDIT_READ","CAP_PERFMON","CAP_BPF","CAP_CHECKPOINT_RESTORE"],"cgroup":{"v1":true,"v2":true,"systemd":true,"systemdUser":true,"rdma":true},"seccomp":{"enabled":true,"actions":["SCMP_ACT_ALLOW","SCMP_ACT_ERRNO","SCMP_ACT_KILL","SCMP_ACT_KILL_PROCESS","SCMP_ACT_KILL_THREAD","SCMP_ACT_LOG","SCMP_ACT_NOTIFY","SCMP_ACT_TRACE","SCMP_ACT_TRAP"],"operators":["SCMP_CMP_EQ","SCMP_CMP_GE","SCMP_CMP_GT","SCMP_CMP_LE","SCMP_CMP_LT","SCMP_CMP_MASKED_EQ","SCMP_CMP_NE"],"archs":["SCMP_ARCH_AARCH64","SCMP_ARCH_ARM","SCMP_ARCH_MIPS","SCMP_ARCH_MIPS64","SCMP_ARCH_MIPS64N32","SCMP_ARCH_MIPSEL","SCMP_ARCH_MIPSEL64","SCMP_ARCH_MIPSEL64N32","SCMP_ARCH_PPC","SCMP_ARCH_PPC64","SCMP_ARCH_PPC64LE","SCMP_ARCH_RISCV64","SCMP_ARCH_S390","SCMP_ARCH_S390X","SCMP_ARCH_X32","SCMP_ARCH_X86","SCMP_ARCH_X86_64"],"knownFlags":["SECCOMP_FILTER_FLAG_TSYNC","SECCOMP_FILTER_FLAG_SPEC_ALLOW","SECCOMP_FILTER_FLAG_LOG"],"supportedFlags":["SECCOMP_FILTER_FLAG_TSYNC","SECCOMP_FILTER_FLAG_SPEC_ALLOW","SECCOMP_FILTER_FLAG_LOG"]},"apparmor":{"enabled":true},"selinux":{"enabled":true},"intelRdt":{"enabled":true},"mountExtensions":{"idmap":{"enabled":true}}},"annotations":{"io.github.seccomp.libseccomp.version":"2.5.5","org.opencontainers.runc.checkpoint.enabled":"true","org.opencontainers.runc.commit":"v1.3.4-0-gd6d73eb8","org.opencontainers.runc.version":"1.3.4\n"},"potentiallyUnsafeConfigAnnotations":["bundle","org.systemd.property.","org.criu.config"]}]}] DefaultRuntime=runc
```

Supporting GPU-runtime facts (not a substitute for the format command above):

```
nvidia-container-toolkit 1.19.1-1 arm64
docker info CDI: nvidia.com/gpu=0 ; nvidia.com/gpu=all
```

### `ip -br link`

```
lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 
enP7s7           UP             4c:bb:47:80:2a:60 <BROADCAST,MULTICAST,UP,LOWER_UP> 
wlP9s9           UP             50:2e:91:5b:48:f4 <BROADCAST,MULTICAST,UP,LOWER_UP> 
tailscale0       UNKNOWN        <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> 
br-3cdf918eb648  DOWN           3e:2b:fe:13:81:df <NO-CARRIER,BROADCAST,MULTICAST,UP> 
br-47b7fb653202  DOWN           22:ee:ec:28:8d:10 <NO-CARRIER,BROADCAST,MULTICAST,UP> 
docker0          DOWN           5a:1d:b0:b1:0b:ec <NO-CARRIER,BROADCAST,MULTICAST,UP> 
```

### ethtool on default route iface

```
$ ethtool "$(ip -br route show default | awk '{print $5; exit}')" 2>/dev/null | egrep 'Speed|Duplex|Link detected' || true
	Speed: 10000Mb/s
	Duplex: Full
	Link detected: yes
```

Default route used by that command (`awk '{print $5; exit}'` takes the first default): `enP7s7`. Extra `ethtool -i enP7s7` for the download-log NIC line:

```
driver: r8127
version: 11.014.00-NAPI
```

---

## Step 2 — GPU-in-container smoke (no H3)

Required command (image already pulled; this is the smoke run):

```bash
docker run --rm --gpus all --platform linux/arm64 \
  nvcr.io/nvidia/pytorch:25.12-py3 \
  python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

Python line (after NGC banner):

```
2.10.0a0+b4e4ee81d3.nv25.12 True NVIDIA GB10
```

NGC banner notes from the same run:

```
NVIDIA Release 25.12 (build 245654591)
PyTorch Version 2.10.0a0+b4e4ee8
NOTE: CUDA Forward Compatibility mode ENABLED.
  Using CUDA 13.1 driver version 590.44.01 with kernel driver version 580.159.03.
```

Extra confirmation (same image, `--gpus all`, `--platform linux/arm64`):

```
cuda_runtime 13.1
device_count 1
capability (12, 1)
```

`docker image inspect nvcr.io/nvidia/pytorch:25.12-py3 --format 'Id={{.Id}} Size={{.Size}} Arch={{.Architecture}} Os={{.Os}} Created={{.Created}}'`:

```
Id=sha256:edda8a492f5b602234cde15ddcc8f1f31562dcbe4eaabfb9433ece2dd21f9780 Size=19727354200 Arch=arm64 Os=linux Created=2025-12-17T08:58:49.831651342Z
```

### Timed pull

`25.12-py3` was **not** local (`25.11-py3` was). First pull, `--platform linux/arm64`:

```
start_utc=2026-08-23T22:26:46Z start_epoch=1787524006.575744549
...
Digest: sha256:1dc787f5c6264fcc1c99809f99b84823e73ed4588d5a581b94290fc2a8fecff8
Status: Downloaded newer image for nvcr.io/nvidia/pytorch:25.12-py3
end_utc=2026-08-23T22:29:48Z end_epoch=1787524188.393676356
pull_rc=0
bytes=19727354200 seconds=181.82 MiB/s=103.5 pct_line=10.9
```

Math (Speed-log protocol): `MiB/s = bytes / seconds / 1048576`; `% of 1000 MB/s = (bytes / seconds / 1e6) / 1000 * 100`. Several layers printed `Already exists` (shared with local `25.11-py3`). Seconds `181.82` ≥ `0.01`, so not `cache-hit`.

---

## Step 3 — Disk headroom

```bash
df -h "$HOME" /var/lib/docker
```

After the NGC pull:

```
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p2  3.7T  982G  2.6T  28% /
/dev/nvme0n1p2  3.7T  982G  2.6T  28% /
```

(Step 1 snapshot before the pull was `967G` used / `2.6T` avail on the same filesystem.)
