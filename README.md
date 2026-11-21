# wheels

Python wheels that Gridline's runtime images pin by exact URL and sha256, published here because their
upstream projects ship them only inside container images. Each wheel is the upstream build, unmodified:
every file it contains is checked against the wheel's own `RECORD`.

## vllm 0.1.dev25855+g7cb5dae22.cu130 (Inkling 2 Mini)

- **What:** the vLLM development build with support for Thinking Machines' Inkling 2 Mini
  (vllm-project/vllm pull request 69028, not yet released), CUDA 13.0, `cp38-abi3`, `Requires-Python >=3.11`.
- **Source:** the wheel installed in `vllm/vllm-openai@sha256:a485440c62099c39659a7b723636073ed726dcb41f94cf6326e16af3a1d6f6bc`
  (Docker Hub), taken from that image's install layer `sha256:7dd4c79b3181…`. The image's build compiled the
  wheel and installed it without publishing it.
- **How it is rebuilt:** `repack_vllm_wheel.py` in this repository. It keeps exactly the files the wheel's
  `RECORD` lists under `vllm/` and its `.dist-info`, refuses any file whose sha256 or size differs from
  `RECORD`, drops only what the installer added (`INSTALLER`, `REQUESTED`, `direct_url.json`, bytecode), and
  writes the archive with fixed timestamps and sorted entries, so the same layer always gives the same bytes.
- **Kernels:** built for compute capability 10.0 and 10.3 (with PTX). Compute capability 12.0 cards need vLLM's
  Triton KV-cache scatter in place of the compiled one; Hopper, Ampere and Ada are not supported by this build.
- **Licence:** vLLM is licensed under the Apache License 2.0 (`LICENSE`); its own licence and notice files are
  inside the wheel's `.dist-info`. Copyright belongs to the vLLM authors.

The release `vllm-0.1.dev25855-g7cb5dae22-cu130` holds the wheel; its sha256 and size are in the release notes.
