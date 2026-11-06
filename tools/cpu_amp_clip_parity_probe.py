#!/usr/bin/env python3
"""Isolated CPU FP32 vs BF16 autocast clipping probe; no network or GPU.

Run: python tools/cpu_amp_clip_parity_probe.py
Requires torch with CPU autocast support. This is NOT a Kaggle CUDA AMP test.
"""
import json

import torch
from torch import nn


def measure(seed, use_bf16):
    torch.manual_seed(seed)
    model = nn.Sequential(nn.Linear(4, 8), nn.Tanh(), nn.Linear(8, 3))
    x = torch.tensor([
        [0.2, -1.1, 0.5, 1.4],
        [-0.6, 0.4, 0.9, -0.2],
        [1.2, -0.8, 0.3, 0.7],
    ], dtype=torch.float32)
    y = torch.tensor([2, 0, 1])
    optimizer = torch.optim.SGD(model.parameters(), lr=0.05)
    initial = [p.detach().clone() for p in model.parameters()]
    with torch.autocast(device_type="cpu", dtype=torch.bfloat16, enabled=use_bf16):
        logits = model(x)
        loss = nn.functional.cross_entropy(logits.float(), y)
    loss.backward()
    grad_norm = lambda: torch.linalg.vector_norm(torch.stack([
        torch.linalg.vector_norm(p.grad.float()) for p in model.parameters()
    ])).item()
    pre = grad_norm()
    returned = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.1).item()
    post = grad_norm()
    optimizer.step()
    update = torch.linalg.vector_norm(torch.stack([
        torch.linalg.vector_norm((p - old).float())
        for p, old in zip(model.parameters(), initial)
    ])).item()
    passed = (
        abs(returned - pre) < 1e-5 and post <= 0.10001 and update > 0
        and all(torch.isfinite(p).all() and torch.isfinite(p.grad).all()
                for p in model.parameters())
    )
    if not passed:
        raise AssertionError(f"Gradient clipping invariant failed for seed={seed}, bf16={use_bf16}")
    return {
        "seed": seed,
        "precision": "cpu_bfloat16_autocast" if use_bf16 else "cpu_fp32",
        "loss": round(loss.item(), 9),
        "pre_grad_norm": round(pre, 9),
        "returned_norm": round(returned, 9),
        "post_grad_norm": round(post, 9),
        "parameter_update_norm": round(update, 9),
        "pass_checks": passed,
    }


def main():
    records = [measure(seed, bf16) for seed in (42, 43, 44) for bf16 in (False, True)]
    print(json.dumps({
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "max_grad_norm": 0.1,
        "learning_rate": 0.05,
        "records": records,
        "all_pass": all(item["pass_checks"] for item in records),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
