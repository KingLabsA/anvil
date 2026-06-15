"""CLI for ShellWhisperer — natural language to shell commands.

Usage:
    sw "find all python files over 100 lines"
    sw --interactive
    sw --train --data ./bash_data.jsonl
    sw --export onnx --model ./models/shell-whisperer-merged
    sw --serve --port 8000
"""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


@click.group(invoke_without_command=True)
@click.option("--interactive", "-i", is_flag=True, help="Start interactive REPL mode")
@click.option("--model", "-m", default=None, help="Path to model directory")
@click.option("--backend", "-b", type=click.Choice(["transformers", "onnx", "llama_cpp"]), default="transformers")
@click.option("--os-type", type=click.Choice(["linux", "macos", "windows"]), default="linux")
@click.option("--temperature", "-t", type=float, default=0.1, help="Sampling temperature")
@click.argument("prompt", required=False)
@click.pass_context
def main(
    ctx: click.Context,
    interactive: bool,
    model: str | None,
    backend: str,
    os_type: str,
    temperature: float,
    prompt: str | None,
) -> None:
    """ShellWhisperer — natural language to shell commands.

    Run `sw "your natural language request"` for one-shot prediction.
    """
    ctx.ensure_object(dict)
    ctx.obj["model_path"] = model or "./models/shell-whisperer-merged"
    ctx.obj["backend"] = backend
    ctx.obj["os_type"] = os_type
    ctx.obj["temperature"] = temperature

    if interactive:
        _interactive_mode(ctx)
        return

    if prompt:
        _oneshot(ctx, prompt)
        return

    # No command specified, show help
    click.echo(ctx.get_help())


@main.command(name="predict")
@click.option("--model", "-m", default=None)
@click.option("--backend", "-b", type=click.Choice(["transformers", "onnx", "llama_cpp"]), default="transformers")
@click.option("--os-type", type=click.Choice(["linux", "macos", "windows"]), default="linux")
@click.argument("prompt")
@click.pass_context
def predict_cmd(ctx: click.Context, model: str | None, backend: str, os_type: str, prompt: str) -> None:
    """Predict a shell command from natural language."""
    from shell_whisperer.inference import Backend, ShellWhisperer

    model_path = model or ctx.obj.get("model_path", "./models/shell-whisperer-merged")

    sw = ShellWhisperer(
        model_path=model_path,
        backend=Backend(backend),
        os_type=os_type,
    )
    sw.load_model()

    result = sw.predict(prompt)

    # Display result
    console.print()
    console.print(Panel(result.command, title="Command", border_style="green"))

    if result.safety_warnings:
        for warning in result.safety_warnings:
            console.print(f"[bold yellow]Warning: {warning}[/bold yellow]")

    console.print(f"[dim]{result.latency_ms:.1f}ms | {result.backend} | {result.os_type}[/dim]")


@main.command(name="train")
@click.option("--data", "-d", multiple=True, help="Path to JSONL training data")
@click.option("--model-name", default="Qwen/Qwen3-1.5B", help="Base model name")
@click.option("--output-dir", default="./models/shell-whisperer-lora", help="Output directory")
@click.option("--epochs", type=int, default=3, help="Number of training epochs")
@click.option("--lr", type=float, default=2e-4, help="Learning rate")
@click.option("--batch-size", type=int, default=4, help="Batch size")
@click.option("--os-type", type=click.Choice(["linux", "macos", "windows"]), default="linux")
@click.option("--full-finetune", is_flag=True, help="Full fine-tune instead of LoRA")
@click.option("--no-builtin", is_flag=True, help="Exclude builtin training pairs")
def train_cmd(
    data: tuple[str, ...],
    model_name: str,
    output_dir: str,
    epochs: int,
    lr: float,
    batch_size: int,
    os_type: str,
    full_finetune: bool,
    no_builtin: bool,
) -> None:
    """Fine-tune the model on shell command data."""
    from shell_whisperer.data_extractor import load_training_data
    from shell_whisperer.trainer import TrainConfig, train_lora

    console.print("[bold]ShellWhisperer Training[/bold]")
    console.print(f"Model: {model_name}")
    console.print(f"Output: {output_dir}")
    console.print(f"Epochs: {epochs}, LR: {lr}, Batch: {batch_size}")

    # Load training data
    training_pairs = load_training_data(
        *data,
        include_builtin=not no_builtin,
    )
    console.print(f"Training pairs: {len(training_pairs)}")

    if not training_pairs:
        console.print("[red]No training data found![/red]")
        sys.exit(1)

    # Show distribution by source
    from collections import Counter
    sources = Counter(p.source for p in training_pairs)
    for source, count in sources.most_common():
        console.print(f"  {source}: {count}")

    config = TrainConfig(
        model_name=model_name,
        output_dir=output_dir,
        epochs=epochs,
        learning_rate=lr,
        batch_size=batch_size,
        full_finetune=full_finetune,
        os_type=os_type,
    )

    output = train_lora(config=config, training_pairs=training_pairs)
    console.print(f"[green]Training complete! Model saved to: {output}[/green]")


@main.command(name="export")
@click.option("--format", "-f", "fmt", type=click.Choice(["onnx", "gguf", "4bit", "8bit", "all"]), required=True)
@click.option("--model", "-m", default="./models/shell-whisperer-merged", help="Path to merged model")
@click.option("--output", "-o", default="./exports", help="Output directory")
def export_cmd(fmt: str, model: str, output: str) -> None:
    """Export model for edge deployment."""
    from shell_whisperer.exporter import estimate_memory, export_all, export_gguf, export_onnx

    console.print(f"[bold]Exporting model: {fmt}[/bold]")
    console.print(f"Model: {model}")
    console.print(f"Output: {output}")

    # Show memory estimates first
    estimates = estimate_memory(model)
    console.print("\n[bold]Memory Estimates:[/bold]")
    for precision, gb in estimates.items():
        if precision != "total_parameters":
            console.print(f"  {precision}: ~{gb} GB")

    if fmt == "onnx":
        path = export_onnx(model, output_path=f"{output}/shell-whisperer.onnx")
        console.print(f"[green]ONNX export: {path}[/green]")

    elif fmt == "gguf":
        path = export_gguf(model, output_path=f"{output}/shell-whisperer.gguf")
        console.print(f"[green]GGUF export: {path}[/green]")

    elif fmt == "4bit":
        from shell_whisperer.exporter import quantize_4bit
        path = quantize_4bit(model, output_path=f"{output}/shell-whisperer-4bit")
        console.print(f"[green]4-bit quantized: {path}[/green]")

    elif fmt == "8bit":
        from shell_whisperer.exporter import quantize_8bit
        path = quantize_8bit(model, output_path=f"{output}/shell-whisperer-8bit")
        console.print(f"[green]8-bit quantized: {path}[/green]")

    elif fmt == "all":
        results = export_all(model, output_dir=output)
        for name, path in results.items():
            if name != "memory_estimates":
                console.print(f"[green]{name}: {path}[/green]")


@main.command(name="serve")
@click.option("--model", "-m", default=None, help="Path to model directory")
@click.option("--backend", "-b", type=click.Choice(["transformers", "onnx", "llama_cpp"]), default="transformers")
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", "-p", type=int, default=8000, help="Port to bind")
@click.option("--os-type", type=click.Choice(["linux", "macos", "windows"]), default="linux")
def serve_cmd(model: str | None, backend: str, host: str, port: int, os_type: str) -> None:
    """Start the FastAPI inference server."""
    import uvicorn

    from shell_whisperer.server import create_app

    model_path = model or "./models/shell-whisperer-merged"

    console.print("[bold]ShellWhisperer Server[/bold]")
    console.print(f"Model: {model_path}")
    console.print(f"Backend: {backend}")
    console.print(f"OS: {os_type}")
    console.print(f"Listening: http://{host}:{port}")

    app = create_app(
        model_path=model_path,
        backend=backend,
        os_type=os_type,
    )

    uvicorn.run(app, host=host, port=port)


def _oneshot(ctx: click.Context, prompt: str) -> None:
    """One-shot prediction from CLI argument."""
    from shell_whisperer.inference import Backend, ShellWhisperer

    model_path = ctx.obj.get("model_path", "./models/shell-whisperer-merged")
    backend = ctx.obj.get("backend", "transformers")
    os_type = ctx.obj.get("os_type", "linux")
    temperature = ctx.obj.get("temperature", 0.1)

    try:
        sw = ShellWhisperer(
            model_path=model_path,
            backend=Backend(backend),
            os_type=os_type,
            temperature=temperature,
        )
        sw.load_model()

        result = sw.predict(prompt)

        console.print()
        console.print(Panel(result.command, title="Command", border_style="green"))

        if result.safety_warnings:
            for warning in result.safety_warnings:
                console.print(f"[bold yellow]Warning: {warning}[/bold yellow]")

        console.print(f"[dim]{result.latency_ms:.1f}ms | {result.backend} | {result.os_type}[/dim]")

        sw.unload()

    except FileNotFoundError:
        console.print(f"[red]Model not found at: {model_path}[/red]")
        console.print("[dim]Run 'sw train' first, or specify --model path[/dim]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def _interactive_mode(ctx: click.Context) -> None:
    """Interactive REPL mode."""
    from shell_whisperer.inference import Backend, ShellWhisperer
    from shell_whisperer.prompts import OPERATING_SYSTEMS

    model_path = ctx.obj.get("model_path", "./models/shell-whisperer-merged")
    backend_str = ctx.obj.get("backend", "transformers")
    os_type = ctx.obj.get("os_type", "linux")
    temperature = ctx.obj.get("temperature", 0.1)

    console.print("[bold]ShellWhisperer Interactive Mode[/bold]")
    console.print(f"Model: {model_path} | OS: {os_type} | Backend: {backend_str}")
    console.print("Type your request in natural language. Ctrl+C to exit.\n")

    try:
        sw = ShellWhisperer(
            model_path=model_path,
            backend=Backend(backend_str),
            os_type=os_type,
            temperature=temperature,
        )
        sw.load_model()
    except FileNotFoundError:
        console.print(f"[red]Model not found at: {model_path}[/red]")
        console.print("[dim]Run 'sw train' first, or specify --model path[/dim]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error loading model: {e}[/red]")
        sys.exit(1)

    history: list[str] = []

    while True:
        try:
            prompt = console.input("[bold green]sw>[/bold green] ")
            if not prompt.strip():
                continue

            if prompt.strip().lower() in ("exit", "quit", "q"):
                break

            if prompt.strip().startswith("!"):
                # Change OS type
                parts = prompt.strip()[1:].split()
                if parts[0] == "os" and len(parts) > 1:
                    new_os = parts[1].lower()
                    if new_os in OPERATING_SYSTEMS:
                        os_type = new_os
                        sw.os_type = os_type
                        console.print(f"[dim]OS set to: {os_type}[/dim]")
                    continue

            result = sw.predict(
                prompt=prompt,
                recent_history=history[-5:] if history else None,
                os_type=os_type,
            )
            history.append(result.command)

            console.print()
            syntax = Syntax(result.command, "bash", theme="monokai", line_numbers=False)
            console.print(Panel(syntax, title="Command", border_style="green"))

            if result.safety_warnings:
                for warning in result.safety_warnings:
                    console.print(f"[bold yellow]Warning: {warning}[/bold yellow]")

            console.print(f"[dim]{result.latency_ms:.1f}ms[/dim]\n")

        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            break
        except EOFError:
            break

    sw.unload()


if __name__ == "__main__":
    main()
