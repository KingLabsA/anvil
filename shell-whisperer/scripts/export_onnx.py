#!/usr/bin/env python3
"""export_onnx.py — Convert ShellWhisperer model to ONNX format for edge deployment.

Exports the fine-tuned model to ONNX, applies graph optimizations,
quantizes to INT8 for mobile/edge inference, and reports model sizes.

Usage:
    python export_onnx.py --model-path PATH --output-dir DIR [--quantize-int8] [--max-seq-length N]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil


def export_to_onnx(model_path: str, output_dir: str, max_seq_length: int = 256):
    """Export HuggingFace model to ONNX format."""
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        print("[ERROR] Install: pip install transformers torch")
        return False

    print(f"Loading model from: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float32,
        trust_remote_code=True,
    )
    model.eval()

    os.makedirs(output_dir, exist_ok=True)

    dummy_input_ids = tokenizer("list all python files", return_tensors="pt")["input_ids"]
    if dummy_input_ids.shape[1] > max_seq_length:
        dummy_input_ids = dummy_input_ids[:, :max_seq_length]

    attention_mask = torch.ones_like(dummy_input_ids)

    onnx_path = os.path.join(output_dir, "model.onnx")

    print(f"Exporting to ONNX (max_seq_length={max_seq_length})...")
    torch.onnx.export(
        model,
        (dummy_input_ids, attention_mask),
        onnx_path,
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch_size", 1: "sequence_length"},
            "attention_mask": {0: "batch_size", 1: "sequence_length"},
            "logits": {0: "batch_size", 1: "sequence_length"},
        },
        opset_version=17,
        do_constant_folding=True,
    )

    original_size = os.path.getsize(onnx_path) / (1024 * 1024)
    print(f"[OK] ONNX model exported: {onnx_path} ({original_size:.1f} MB)")

    tokenizer.save_pretrained(output_dir)

    try:
        from onnxruntime.transformers import optimizer as ort_optimizer
        from onnxruntime.transformers.fusion_options import FusionOptions

        print("Applying ONNX graph optimizations...")
        opt_output = os.path.join(output_dir, "model_optimized.onnx")

        fused_model = ort_optimizer.optimize_model(
            onnx_path,
            model_type="gpt2",
            num_heads=model.config.num_attention_heads if hasattr(model.config, "num_attention_heads") else 12,
            hidden_size=model.config.hidden_size if hasattr(model.config, "hidden_size") else 1536,
        )
        fused_model.save_model_to_file(opt_output)

        opt_size = os.path.getsize(opt_output) / (1024 * 1024)
        print(f"[OK] Optimized ONNX: {opt_output} ({opt_size:.1f} MB)")
    except ImportError:
        print("[WARN] onnxruntime.transformers not available, skipping graph optimization")
        print("       Install with: pip install onnxruntime-transformers")
    except Exception as e:
        print(f"[WARN] Graph optimization failed: {e}")

    return onnx_path


def quantize_onnx_int8(onnx_path: str, output_dir: str):
    """Quantize ONNX model to INT8 for edge deployment."""
    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic
    except ImportError:
        print("[ERROR] Install: pip install onnxruntime")
        return None

    quantized_path = os.path.join(output_dir, "model_quantized.onnx")

    print("Quantizing to INT8...")
    quantize_dynamic(
        model_input=onnx_path,
        model_output=quantized_path,
        weight_type=QuantType.QInt8,
        per_channel=True,
        reduce_range=True,
    )

    quant_size = os.path.getsize(quantized_path) / (1024 * 1024)
    original_size = os.path.getsize(onnx_path) / (1024 * 1024)
    reduction = (1 - quant_size / original_size) * 100

    print(f"[OK] INT8 quantized model: {quantized_path} ({quant_size:.1f} MB)")
    print(f"     Size reduction: {reduction:.0f}% ({original_size:.1f} MB -> {quant_size:.1f} MB)")

    return quantized_path


def create_tokenizer_files(output_dir: str, tokenizer):
    """Create minimal tokenizer files for edge deployment."""
    vocab_path = os.path.join(output_dir, "tokenizer.json")
    if os.path.exists(vocab_path):
        print(f"[OK] Tokenizer files already in {output_dir}")
        return

    print("[INFO] Copying tokenizer files for edge deployment...")


def benchmark_onnx(onnx_path: str, tokenizer_path: str, max_seq_length: int = 64):
    """Benchmark ONNX model inference latency."""
    try:
        import time

        import numpy as np
        import onnxruntime as ort
    except ImportError:
        print("[WARN] onnxruntime not available for benchmarking")
        return

    print("\n=== ONNX Inference Benchmark ===")
    print(f"  Model: {onnx_path}")

    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    try:
        session = ort.InferenceSession(onnx_path, sess_options, providers=["CPUExecutionProvider"])
    except Exception as e:
        print(f"[ERROR] Failed to create ONNX session: {e}")
        return

    input_ids = np.array([[1] + [0] * (max_seq_length - 1)], dtype=np.int64)
    attention_mask = np.ones((1, max_seq_length), dtype=np.int64)

    warmup_runs = 5
    for _ in range(warmup_runs):
        session.run(None, {"input_ids": input_ids, "attention_mask": attention_mask})

    num_runs = 50
    latencies = []
    for _ in range(num_runs):
        start = time.perf_counter()
        session.run(None, {"input_ids": input_ids, "attention_mask": attention_mask})
        latencies.append((time.perf_counter() - start) * 1000)

    avg_ms = sum(latencies) / len(latencies)
    p50 = sorted(latencies)[len(latencies) // 2]
    p95 = sorted(latencies)[int(len(latencies) * 0.95)]
    p99 = sorted(latencies)[int(len(latencies) * 0.99)]

    print(f"  Runs: {num_runs}")
    print(f"  Avg:  {avg_ms:.1f}ms")
    print(f"  P50:  {p50:.1f}ms")
    print(f"  P95:  {p95:.1f}ms")
    print(f"  P99:  {p99:.1f}ms")

    target_ms = 50.0
    if p50 < target_ms:
        print(f"  [PASS] P50 latency < {target_ms}ms target")
    else:
        print(f"  [WARN] P50 latency {p50:.1f}ms exceeds {target_ms}ms target")

    bench_path = os.path.join(os.path.dirname(onnx_path), "benchmark_results.json")
    results = {
        "model": os.path.basename(onnx_path),
        "max_seq_length": max_seq_length,
        "num_runs": num_runs,
        "avg_ms": round(avg_ms, 1),
        "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1),
        "p99_ms": round(p99, 1),
        "target_ms": target_ms,
        "pass": p50 < target_ms,
    }
    with open(bench_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  Results saved to: {bench_path}")


def create_edge_deploy_package(output_dir: str, quantized_path: str, tokenizer_path: str):
    """Create a deployment package for edge devices."""
    deploy_dir = os.path.join(output_dir, "edge_deploy")
    os.makedirs(deploy_dir, exist_ok=True)

    if quantized_path and os.path.exists(quantized_path):
        shutil.copy2(quantized_path, os.path.join(deploy_dir, "model.onnx"))

    tokenizer_files = ["tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "tokenizer.model"]
    for tf in tokenizer_files:
        src = os.path.join(tokenizer_path, tf) if tokenizer_path else os.path.join(output_dir, tf)
        dst = os.path.join(deploy_dir, tf)
        if os.path.exists(src):
            shutil.copy2(src, dst)

    config = {
        "model_type": "shell-whisperer",
        "architecture": "qwen2",
        "max_seq_length": 256,
        "target_latency_ms": 50,
        "target_platforms": ["raspberry-pi-4", "iphone-15", "android-flagship"],
        "input_format": {
            "instruction": "string - natural language description of the command",
            "input": "string - optional context (working directory, OS type)",
        },
        "output_format": {
            "output": "string - shell command",
        },
    }
    with open(os.path.join(deploy_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    example_code = '''#!/usr/bin/env python3
"""ShellWhisperer edge inference example."""

import json
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    raise ImportError("Install: pip install onnxruntime")

from transformers import AutoTokenizer


class ShellWhisperer:
    def __init__(self, model_dir: str = "edge_deploy"):
        self.session = ort.InferenceSession(
            f"{model_dir}/model.onnx",
            providers=["CPUExecutionProvider"],
        )
        with open(f"{model_dir}/config.json") as f:
            self.config = json.load(f)
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)

    def predict(self, instruction: str, context: str = "") -> str:
        prompt = f"### Instruction:\\n{instruction}\\n\\n### Response:\\n"
        if context:
            prompt = f"### Instruction:\\n{instruction}\\n\\n### Input:\\n{context}\\n\\n### Response:\\n"

        inputs = self.tokenizer(prompt, return_tensors="np", max_length=256, truncation=True)
        outputs = self.session.run(
            None,
            {"input_ids": inputs["input_ids"], "attention_mask": inputs["attention_mask"]},
        )
        generated_ids = np.argmax(outputs[0], axis=-1)
        return self.tokenizer.decode(generated_ids[0], skip_special_tokens=True)


if __name__ == "__main__":
    model = ShellWhisperer()
    result = model.predict("find all python files over 100 lines", context="linux")
    print(f"Command: {result}")
'''
    with open(os.path.join(deploy_dir, "infer.py"), "w") as f:
        f.write(example_code)

    print(f"[OK] Edge deployment package created: {deploy_dir}")
    print("     Contents:")
    for f in sorted(os.listdir(deploy_dir)):
        size = os.path.getsize(os.path.join(deploy_dir, f))
        print(f"       {f}  ({size / 1024:.1f} KB)")


def main():
    parser = argparse.ArgumentParser(description="Export ShellWhisperer to ONNX for edge deployment")
    parser.add_argument("--model-path", required=True, help="Path to the fine-tuned model")
    parser.add_argument("--output-dir", required=True, help="Output directory for ONNX files")
    parser.add_argument("--quantize-int8", action="store_true", help="Apply INT8 quantization")
    parser.add_argument("--max-seq-length", type=int, default=256, help="Maximum sequence length for export")
    parser.add_argument("--skip-benchmark", action="store_true", help="Skip latency benchmark")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    onnx_path = export_to_onnx(args.model_path, args.output_dir, args.max_seq_length)
    if not onnx_path:
        print("[ERROR] ONNX export failed")
        return 1

    quantized_path = None
    if args.quantize_int8:
        quantized_path = quantize_onnx_int8(onnx_path, args.output_dir)

    if not args.skip_benchmark:
        benchmark_path = quantized_path or onnx_path
        benchmark_onnx(benchmark_path, args.model_path, max_seq_length=min(args.max_seq_length, 64))

    create_edge_deploy_package(args.output_dir, quantized_path or onnx_path, args.model_path)

    print("\n=== Export Summary ===")
    for f in sorted(os.listdir(args.output_dir)):
        fpath = os.path.join(args.output_dir, f)
        if os.path.isfile(fpath):
            size_mb = os.path.getsize(fpath) / (1024 * 1024)
            if size_mb >= 0.1:
                print(f"  {f}: {size_mb:.1f} MB")

    return 0


if __name__ == "__main__":
    exit(main())
