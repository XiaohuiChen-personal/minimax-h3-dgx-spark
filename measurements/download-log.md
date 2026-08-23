# Download speed log — DGX Spark ethernet

Plan: 8 Gbps (1000 MB/s line-rate ceiling).
NIC (from Task 1): 10000Mb/s Full, driver r8127 11.014.00-NAPI, iface enP7s7
Method: wall-clock around the transfer; bytes from the finished file or `docker image inspect`.

| When (UTC) | Artifact | Source | Bytes | Seconds | MiB/s | % of 1000 MB/s | Notes |
|---|---|---|---:|---:|---:|---:|---|
| 2026-08-23T22:26:46Z | nvcr.io/nvidia/pytorch:25.12-py3 | nvcr.io | 19727354200 | 181.82 | 103.5 | 10.9 | linux/arm64; inspect Size; some layers already existed from local 25.11-py3 |
