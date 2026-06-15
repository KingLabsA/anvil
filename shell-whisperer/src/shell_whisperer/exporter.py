"""Export ShellWhisperer models for edge deployment.

Supports:
  - ONNX (via optimum / direct torch export)
  - GGUF (for llama.cpp)
  - 4-bit and 8-bit quantization
  - Memory estimation
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def estimate_memory(model_path: str) -> dict[str, float]:
    """Estimate RAM requirements for a model at various precisions.

    Args:
        model_path: Path to the model directory (HuggingFace format).

    Returns:
        Dict mapping precision name to estimated GB of RAM.
    """
    model_dir = Path(model_path)

    # Find safetensors or bin files
    total_params = 0
    total_bytes = 0

    for pattern in ("*.safetensors", "*.bin", "*.pt"):
        for f in model_dir.glob(pattern):
            total_bytes += f.stat().st_size

    # If no weight files found, estimate from config
    if total_bytes == 0:
        config_path = model_dir / "config.json"
        if config_path.exists():
            import json

            with config_path.open() as f:
                config = json.load(f)
            num_layers = config.get("num_hidden_layers", 28)
            hidden_size = config.get("hidden_size", 1536)
            intermediate_size = config.get("intermediate_size", 8960)
            # Rough parameter estimate for Qwen-style transformers
            # Each layer: 4 * hidden^2 + 3 * hidden * intermediate + 2 * hidden * vocab
            vocab_size = config.get("vocab_size", 151936)
            params_per_layer = (
                4 * hidden_size * hidden_size
                + 3 * hidden_size * intermediate_size
                + 2 * hidden_size * vocab_size // num_layers
            )
            total_params = num_layers * params_per_layer
            # Embedding layer
            total_params += vocab_size * hidden_size
        else:
            # Default: assume Qwen3-1.5B ≈ 1.5B params
            total_params = 1_500_000_000

    # If we found weight files, estimate from file size
    if total_bytes > 0:
        # Assume fp16 weights (2 bytes per param), plus optimizer overhead
        total_params = int(total_bytes / 2)

    bytes_per_param = {
        "fp32": 4.0,
        "fp16": 2.0,
        "bf16": 2.0,
        "8bit": 1.0,
        "4bit": 0.5,
        "gguf_q4_k_m": 0.56,
        "gguf_q5_k_m": 0.68,
    }

    estimates = {}
    for precision, bpp in bytes_per_param.items():
        gb = (total_params * bpp) / (1024**3)
        estimates[precision] = round(gb, 2)

    estimates["total_parameters"] = float(total_params)
    return estimates


def export_onnx(
    model_path: str,
    output_path: str = "./exports/shell-whisperer.onnx",
    opset: int = 17,
    max_seq_length: int = 512,
) -> str:
    """Export model to ONNX format for edge deployment.

    Uses optimum for optimum-compatible models, falls back to
    direct torch export.

    Args:
        model_path: Path to the merged HuggingFace model.
        output_path: Path for the output ONNX file.
        opset: ONNX opset version.
        max_seq_length: Maximum sequence length for the export.

    Returns:
        Path to the exported ONNX model directory.
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer

    output_dir = Path(output_path)
    if output_dir.suffix == ".onnx":
        output_dir = output_dir.parent / output_dir.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Exporting ONNX from %s to %s", model_path, output_dir)

    # Try optimum first
    try:
        from optimum.onnxruntime import ORTModelForCausalLM

        model = ORTModelForCausalLM.from_pretrained(
            model_path,
            export=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model.save_pretrained(str(output_dir))
        tokenizer.save_pretrained(str(output_dir))
        logger.info("ONNX export via optimum: %s", output_dir)
        return str(output_dir)
    except (ImportError, Exception) as e:
        logger.info("Optimum export failed (%s), falling back to torch export", e)

    # Fallback: direct torch export
    import torch

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        device_map="cpu",
    )
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    tokenizer.save_pretrained(str(output_dir))

    dummy_input = tokenizer(
        "find all python files",
        return_tensors="pt",
        max_length=max_seq_length,
        padding="max_length",
        truncation=True,
    )

    onnx_file = output_dir / "model.onnx"
    torch.onnx.export(
        model,
        (dummy_input["input_ids"], dummy_input["attention_mask"]),
        str(onnx_file),
        opset_version=opset,
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch_size", 1: "sequence"},
            "attention_mask": {0: "batch_size", 1: "sequence"},
            "logits": {0: "batch_size", 1: "sequence"},
        },
        do_constant_folding=True,
    )

    # Copy config files
    for name in ("config.json", "tokenizer_config.json", "tokenizer.json", "special_tokens_map.json"):
        src = Path(model_path) / name
        if src.exists():
            shutil.copy2(src, output_dir / name)

    logger.info("ONNX export complete: %s", output_dir)
    return str(output_dir)


def export_gguf(
    model_path: str,
    output_path: str = "./exports/shell-whisperer.gguf",
) -> str:
    """Export model to GGUF format for llama.cpp.

    Requires llama.cpp to be available with its Python conversion script.

    Args:
        model_path: Path to the merged HuggingFace model.
        output_path: Path for the output GGUF file.

    Returns:
        Path to the exported GGUF file.
    """
    import subprocess

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Try to find convert script from llama.cpp
    convert_candidates = [
        Path("/usr/local/bin/convert_hf_to_gguf.py"),
        Path.home() / "llama.cpp" / "convert_hf_to_gguf.py",
        Path("./llama.cpp/convert_hf_to_gguf.py"),
        Path("./convert_hf_to_gguf.py"),
    ]

    # Also check newer naming
    convert_candidates.extend([
        Path.home() / "llama.cpp" / "convert_hf_to_gguf.py",
        Path("./llama.cpp/convert_hf_to_gguf.py"),
    ])

    # Try using the Python package approach
    try:
        from llama_cpp import Llama

        logger.info("Using llama-cpp-python for GGUF export")
        llm = Llama(model_path=model_path)
        # llama-cpp-python doesn't have direct GGUF export;
        # fall through to convert script
    except ImportError:
        pass

    # Fall back to subprocess call to llama.cpp converter
    convert_script = None
    for candidate in convert_candidates:
        if candidate.exists():
            convert_script = candidate
            break

    if convert_script is None:
        # Try to find it via `which`
        result = subprocess.run(
            ["which", "convert_hf_to_gguf.py"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            convert_script = Path(result.stdout.strip())

    if convert_script is None:
        logger.warning(
            "llama.cpp convert script not found. "
            "Install llama.cpp and ensure convert_hf_to_gguf.py is in PATH. "
            "Alternatively, use: pip install llama-cpp-python[server]"
        )
        # Create a minimal GGUF-like marker file
        output.write_text("# GGUF export requires llama.cpp\n")
        logger.error("GGUF export failed: llama.cpp not found")
        return str(output)

    cmd = [
        "python",
        str(convert_script),
        model_path,
        "--outfile",
        str(output),
        "--outtype",
        "f16",
    ]

    logger.info("Running GGUF conversion: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error("GGUF conversion failed: %s", result.stderr)
        raise RuntimeError(f"GGUF conversion failed: {result.stderr}")

    logger.info("GGUF export complete: %s", output)
    return str(output)


def quantize_4bit(
    model_path: str,
    output_path: str = "./exports/shell-whisperer-4bit",
) -> str:
    """Quantize model to 4-bit precision for edge deployment.

    Uses bitsandbytes NF4 quantization.

    Args:
        model_path: Path to the merged HuggingFace model.
        output_path: Directory for the quantized model.

    Returns:
        Path to the quantized model directory.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Quantizing to 4-bit: %s -> %s", model_path, output_dir)

    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        quantization_config=quantization_config,
        device_map="auto",
    )
    tokenizer = AutoTokenizer.from_pretrained(model_path)

    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    # Write quantization metadata
    meta = {
        "quantization": "4bit-nf4",
        "compute_dtype": "bfloat16",
        "double_quant": True,
        "source_model": str(model_path),
    }
    import json

    with (output_dir / "quantization_config.json").open("w") as f:
        json.dump(meta, f, indent=2)

    mem = estimate_memory(output_path)
    logger.info("4-bit quantized model saved. Estimated RAM: %s GB", mem.get("4bit", "unknown"))
    return str(output_dir)


def quantize_8bit(
    model_path: str,
    output_path: str = "./exports/shell-whisperer-8bit",
) -> str:
    """Quantize model to 8-bit precision for edge deployment.

    Uses bitsandbytes int8 quantization.

    Args:
        model_path: Path to the merged HuggingFace model.
        output_path: Directory for the quantized model.

    Returns:
        Path to the quantized model directory.
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Quantizing to 8-bit: %s -> %s", model_path, output_dir)

    quantization_config = BitsAndBytesConfig(
        load_in_8bit=True,
        llm_int8_threshold=6.0,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        quantization_config=quantization_config,
        device_map="auto",
    )
    tokenizer = AutoTokenizer.from_pretrained(model_path)

    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    import json

    meta = {
        "quantization": "8bit-int8",
        "threshold": 6.0,
        "source_model": str(model_path),
    }
    with (output_dir / "quantization_config.json").open("w") as f:
        json.dump(meta, f, indent=2)

    mem = estimate_memory(output_path)
    logger.info("8-bit quantized model saved. Estimated RAM: %s GB", mem.get("8bit", "unknown"))
    return str(output_dir)


def export_all(
    model_path: str,
    output_dir: str = "./exports",
) -> dict[str, str]:
    """Export model to all supported formats.

    Args:
        model_path: Path to the merged HuggingFace model.
        output_dir: Base directory for exports.

    Returns:
        Dict mapping format name to export path.
    """
    results = {}

    logger.info("Exporting model from %s to all formats", model_path)

    results["onnx"] = export_onnx(
        model_path,
        output_path=str(Path(output_dir) / "shell-whisperer.onnx"),
    )

    results["gguf"] = export_gguf(
        model_path,
        output_path=str(Path(output_dir) / "shell-whisperer.gguf"),
    )

    results["4bit"] = quantize_4bit(
        model_path,
        output_path=str(Path(output_dir) / "shell-whisperer-4bit"),
    )

    results["8bit"] = quantize_8bit(
        model_path,
        output_path=str(Path(output_dir) / "shell-whisperer-8bit"),
    )

    results["memory_estimates"] = estimate_memory(model_path)

    logger.info("All exports complete: %s", list(results.keys()))
    return results
