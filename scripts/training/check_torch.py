#!/usr/bin/env python3
"""Print PyTorch device capability for this environment."""

from __future__ import annotations

import torch


def main() -> None:
    print(f"torch_version={torch.__version__}")
    print(f"torch_cuda_version={torch.version.cuda}")
    print(f"cuda_available={torch.cuda.is_available()}")
    print(f"cuda_device_count={torch.cuda.device_count()}")
    for index in range(torch.cuda.device_count()):
        print(f"cuda_device_{index}_name={torch.cuda.get_device_name(index)}")
        print(f"cuda_device_{index}_capability={torch.cuda.get_device_capability(index)}")

    selected = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"training_device_auto={selected}")


if __name__ == "__main__":
    main()
