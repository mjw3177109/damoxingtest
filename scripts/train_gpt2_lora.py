#!/usr/bin/env python3
"""Reproducible small-scale Chinese GPT-2 LoRA fine-tuning and evaluation."""
import argparse
import hashlib
import json
import logging
import math
import os
import random
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

MODEL_DEFAULT = "uer/gpt2-chinese-cluecorpussmall"
SEED_DEFAULT = 42
PROJECT_PRINCIPLES = [
    "保护用户：保护隐私、数据、账户与合法权益。",
    "维护人类：尊重生命、尊严、自由与安全。",
]


def write_json(path, payload):
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def write_stage(output_dir, filename, title, body):
    stage_dir = Path(output_dir) / "stages"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / (filename + ".md")).write_text(
        "# " + title + "\n\n" + body + "\n",
        encoding="utf-8",
    )


def setup_logger(output_dir):
    logger = logging.getLogger("gpt2_lora_training")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    file_handler = logging.FileHandler(output_dir / "training.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(stream)
    logger.addHandler(file_handler)
    return logger


def safe_ppl(loss):
    if loss is None or not math.isfinite(float(loss)):
        return None
    if float(loss) > 50:
        return None
    return float(math.exp(float(loss)))


def run(args):
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(output_dir)
    start_time = time.time()

    import torch
    from datasets import Dataset
    from peft import LoraConfig, PeftModel, TaskType, get_peft_model
    from transformers import (
        TrainerCallback,
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    class FileLoggingCallback(TrainerCallback):
        def __init__(self, target_logger):
            self.target_logger = target_logger

        def on_log(self, args, state, control, logs=None, **kwargs):
            if logs:
                self.target_logger.info("Trainer metrics at step %s: %s", state.global_step, logs)
            return control

    set_seed(args.seed)
    random.seed(args.seed)

    cuda_available = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if cuda_available else None
    gpu_memory_gib = (
        round(torch.cuda.get_device_properties(0).total_memory / (1024 ** 3), 2)
        if cuda_available
        else None
    )
    metadata = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_name": args.model_name,
        "training_method": "LoRA supervised causal language-model fine-tuning",
        "project_principles": PROJECT_PRINCIPLES,
        "seed": args.seed,
        "max_length": args.max_length,
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "per_device_train_batch_size": args.batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "lora_rank": args.lora_rank,
        "lora_alpha": args.lora_alpha,
        "lora_dropout": args.lora_dropout,
        "cuda_available": cuda_available,
        "gpu_name": gpu_name,
        "gpu_memory_gib": gpu_memory_gib,
        "torch_version": torch.__version__,
        "python_version": sys.version,
    }
    write_json(output_dir / "run_metadata.json", metadata)
    write_stage(output_dir, "stage0_environment", "阶段 0：环境与 GPU 检查", "状态：检查中。目标为 NVIDIA T4，约 16GB 显存。实际 GPU：" + str(gpu_name) + "；显存 GiB：" + str(gpu_memory_gib) + "。")
    logger.info("Starting GPT-2 LoRA training.")
    logger.info("Model: %s", args.model_name)
    logger.info("CUDA available: %s", cuda_available)
    logger.info("GPU: %s; memory GiB: %s", gpu_name, gpu_memory_gib)

    if args.require_gpu and not cuda_available:
        write_stage(output_dir, "stage0_environment", "阶段 0：环境与 GPU 检查", "状态：阻塞。需要 GPU，但 CUDA 不可用。未开始训练。")
        raise RuntimeError("GPU is required but CUDA is unavailable.")
    if args.require_t4:
        if not cuda_available:
            write_stage(output_dir, "stage0_environment", "阶段 0：环境与 GPU 检查", "状态：阻塞。需要 NVIDIA T4，但没有 CUDA GPU。未开始训练。")
            raise RuntimeError("NVIDIA T4 is required but no CUDA GPU is available.")
        if "T4" not in str(gpu_name).upper():
            write_stage(output_dir, "stage0_environment", "阶段 0：环境与 GPU 检查", "状态：阻塞。目标为 NVIDIA T4，实际分配为 " + str(gpu_name) + "。未开始训练。")
            raise RuntimeError("NVIDIA T4 is required; actual GPU is: " + str(gpu_name))
    write_stage(output_dir, "stage0_environment", "阶段 0：环境与 GPU 检查", "状态：通过。实际 GPU：" + str(gpu_name) + "；显存 GiB：" + str(gpu_memory_gib) + "。")

    corpus_path = Path(args.data).resolve()
    if not corpus_path.exists():
        raise FileNotFoundError("Training corpus not found: " + str(corpus_path))
    corpus_sha256 = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    metadata["training_data_sha256"] = corpus_sha256
    write_json(output_dir / "run_metadata.json", metadata)
    logger.info("Training corpus SHA-256: %s", corpus_sha256)

    def load_jsonl(path):
        loaded = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid JSONL at " + str(path) + ":" + str(line_number)) from exc
            if not isinstance(item, dict) or not item.get("instruction") or not item.get("response"):
                raise ValueError("Each record must contain instruction and response: " + str(path))
            loaded.append(item)
        return loaded

    training_records = load_jsonl(corpus_path)
    if len(training_records) < 80:
        raise ValueError("Training corpus must contain at least 80 curated records.")
    eval_path = Path(args.eval_data).resolve() if args.eval_data else None
    if eval_path is None or not eval_path.exists():
        raise FileNotFoundError("Fixed holdout evaluation corpus not found: " + str(eval_path))
    validation_records = load_jsonl(eval_path)
    if len(validation_records) < 20:
        raise ValueError("Fixed holdout evaluation corpus must contain at least 20 records.")
    normalize_instruction = lambda value: "".join(value.casefold().split())
    train_instructions = {normalize_instruction(item["instruction"]) for item in training_records}
    eval_instructions = {normalize_instruction(item["instruction"]) for item in validation_records}
    overlap = train_instructions.intersection(eval_instructions)
    if overlap:
        raise ValueError("Training/evaluation leakage detected: " + str(len(overlap)) + " duplicate normalized instructions.")
    corpus_sha256 = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    eval_sha256 = hashlib.sha256(eval_path.read_bytes()).hexdigest()
    metadata["training_data_sha256"] = corpus_sha256
    metadata["eval_data_sha256"] = eval_sha256
    metadata["training_corpus_path"] = corpus_path.name
    metadata["eval_corpus_path"] = eval_path.name
    metadata["training_record_count"] = len(training_records)
    metadata["evaluation_record_count"] = len(validation_records)
    write_json(output_dir / "run_metadata.json", metadata)
    logger.info("Training corpus SHA-256: %s", corpus_sha256)
    logger.info("Fixed evaluation corpus SHA-256: %s", eval_sha256)
    logger.info("Loaded fixed corpora: train=%s, validation=%s", len(training_records), len(validation_records))
    write_stage(output_dir, "stage1_data_prep", "阶段 1：数据准备", "状态：完成。训练样本：" + str(len(training_records)) + "；固定验证样本：" + str(len(validation_records)) + "；训练数据 SHA-256：" + corpus_sha256 + "；验证数据 SHA-256：" + eval_sha256 + "。训练与验证指令已执行重叠检查。")

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
    if tokenizer.eos_token is None:
        if tokenizer.sep_token is not None:
            tokenizer.eos_token = tokenizer.sep_token
        else:
            tokenizer.add_special_tokens({"eos_token": "<|endoftext|>"})
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def encode_record(record):
        prefix = "用户：" + record["instruction"] + "\n助手："
        answer = record["response"] + str(tokenizer.eos_token)
        prefix_ids = tokenizer(prefix, add_special_tokens=False)["input_ids"]
        answer_ids = tokenizer(answer, add_special_tokens=False)["input_ids"]
        input_ids = (prefix_ids + answer_ids)[:args.max_length]
        labels = ([-100] * len(prefix_ids) + answer_ids)[:args.max_length]
        if not any(label != -100 for label in labels):
            raise ValueError("Record has no response tokens after truncation: " + record["instruction"])
        return {"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels}

    train_dataset = Dataset.from_list([encode_record(x) for x in training_records])
    eval_dataset = Dataset.from_list([encode_record(x) for x in validation_records])

    def response_only_collator(features):
        max_len = max(len(item["input_ids"]) for item in features)
        batch_size = len(features)
        input_ids = torch.full((batch_size, max_len), tokenizer.pad_token_id, dtype=torch.long)
        attention_mask = torch.zeros((batch_size, max_len), dtype=torch.long)
        labels = torch.full((batch_size, max_len), -100, dtype=torch.long)
        for index, item in enumerate(features):
            size = len(item["input_ids"])
            input_ids[index, :size] = torch.tensor(item["input_ids"], dtype=torch.long)
            attention_mask[index, :size] = torch.tensor(item["attention_mask"], dtype=torch.long)
            labels[index, :size] = torch.tensor(item["labels"], dtype=torch.long)
        return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}

    logger.info("Loading base model weights.")
    model = AutoModelForCausalLM.from_pretrained(args.model_name)
    resolved_model_commit = getattr(model.config, "_commit_hash", None)
    metadata["resolved_model_commit"] = resolved_model_commit
    write_json(output_dir / "run_metadata.json", metadata)
    logger.info("Resolved model commit: %s", resolved_model_commit)
    if model.get_input_embeddings().num_embeddings != len(tokenizer):
        model.resize_token_embeddings(len(tokenizer))
    model.config.pad_token_id = tokenizer.pad_token_id
    model.config.use_cache = False

    adapter_path = Path(args.adapter_path).resolve() if args.adapter_path else None
    starting_adapter_loaded = False
    starting_adapter_sha256 = None
    if adapter_path is not None:
        if not (adapter_path / "adapter_config.json").is_file():
            raise FileNotFoundError("Requested approved adapter is missing adapter_config.json: " + str(adapter_path))
        model = PeftModel.from_pretrained(model, str(adapter_path), is_trainable=True)
        starting_adapter_loaded = True
        adapter_hashes = []
        for adapter_file in sorted(adapter_path.rglob("*")):
            if adapter_file.is_file():
                adapter_hashes.append((str(adapter_file.relative_to(adapter_path)), hashlib.sha256(adapter_file.read_bytes()).hexdigest()))
        starting_adapter_sha256 = hashlib.sha256(json.dumps(adapter_hashes, ensure_ascii=False).encode("utf-8")).hexdigest()
        logger.info("Loaded approved previous adapter from %s", adapter_path)
    else:
        lora_config = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=args.lora_rank,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            target_modules=["c_attn", "c_proj"],
            fan_in_fan_out=True,
        )
        model = get_peft_model(model, lora_config)
        logger.info("No approved prior adapter found; training a new candidate from the base model.")
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=str(output_dir / "trainer_state"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.eval_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        warmup_ratio=0.05,
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        max_grad_norm=1.0,
        evaluation_strategy="epoch",
        save_strategy="no",
        logging_strategy="steps",
        logging_steps=args.logging_steps,
        logging_first_step=True,
        fp16=bool(cuda_available),
        bf16=False,
        optim="adamw_torch",
        report_to="none",
        seed=args.seed,
        data_seed=args.seed,
        dataloader_pin_memory=bool(cuda_available),
        remove_unused_columns=True,
    )
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=response_only_collator,
        tokenizer=tokenizer,
    )

    logger.info("Evaluating the base model before fine-tuning.")
    base_eval = trainer.evaluate()
    base_loss = float(base_eval["eval_loss"])
    logger.info("Base validation loss: %.6f; PPL: %s", base_loss, safe_ppl(base_loss))
    write_stage(output_dir, "stage2_base_evaluation", "阶段 2：基础模型基线评估", "状态：完成。基线验证集 loss：" + str(round(base_loss, 6)) + "；基线 PPL：" + str(safe_ppl(base_loss)) + "。验证集未用于梯度更新。")

    logger.info("Beginning LoRA fine-tuning.")
    trainer.add_callback(FileLoggingCallback(logger))
    train_result = trainer.train()
    train_loss_stage = train_result.metrics.get("train_loss")
    logger.info("Training completed: global_step=%s; train_loss=%s", train_result.global_step, train_loss_stage)
    write_stage(output_dir, "stage3_lora_training", "阶段 3：LoRA 微调", "状态：完成。训练轮数：" + str(args.epochs) + "；学习率：" + str(args.learning_rate) + "；LoRA rank：" + str(args.lora_rank) + "；训练 loss：" + str(train_loss_stage) + "。Adapter 保存在本次运行输出中。")
    logger.info("Fine-tuning finished; evaluating again.")
    final_eval = trainer.evaluate()
    final_loss = float(final_eval["eval_loss"])

    adapter_dir = output_dir / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    trainer.model.config.use_cache = True
    trainer.model.eval()
    prompts = ["用户：" + item["instruction"] + "\n助手：" for item in validation_records[:10]]
    samples = []
    device = next(trainer.model.parameters()).device
    for prompt in prompts:
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            generated = trainer.model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                repetition_penalty=1.12,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        continuation = generated[0][inputs["input_ids"].shape[1]:]
        output_text = tokenizer.decode(continuation, skip_special_tokens=True).strip()
        samples.append({
            "prompt": prompt,
            "output": output_text,
            "manual_review_required": True,
            "note": "自动生成样例不是安全认证，必须人工复核。",
        })

    duration = round(time.time() - start_time, 2)
    metrics = {
        "model_name": args.model_name,
        "training_method": "LoRA supervised causal language-model fine-tuning",
        "project_principles": PROJECT_PRINCIPLES,
        "training_data_sha256": corpus_sha256,
        "eval_data_sha256": eval_sha256,
        "resolved_model_commit": resolved_model_commit,
        "starting_adapter_loaded": starting_adapter_loaded,
        "starting_adapter_sha256": starting_adapter_sha256,
        "starting_model_state": "approved_previous_adapter" if starting_adapter_loaded else "base_model",
        "train_examples": len(training_records),
        "validation_examples": len(validation_records),
        "epochs": args.epochs,
        "learning_rate": args.learning_rate,
        "lora_rank": args.lora_rank,
        "max_length": args.max_length,
        "base_eval_loss": base_loss,
        "final_eval_loss": final_loss,
        "base_eval_ppl": safe_ppl(base_loss),
        "final_eval_ppl": safe_ppl(final_loss),
        "eval_loss_improvement_pct": round((base_loss - final_loss) / max(abs(base_loss), 1e-12) * 100, 3),
        "train_loss": float(train_result.metrics.get("train_loss", 0.0)),
        "train_steps": int(train_result.global_step),
        "train_runtime_seconds": duration,
        "gpu_name": gpu_name,
        "gpu_memory_gib": gpu_memory_gib,
        "seed": args.seed,
        "interpretation": "Small seed-corpus metrics only; not evidence of general capability or safety.",
    }
    write_json(output_dir / "metrics.json", metrics)
    write_json(output_dir / "samples.json", samples)
    loss_change = metrics["eval_loss_improvement_pct"]
    write_stage(output_dir, "stage4_evaluation", "阶段 4：评估与模型输出", "状态：完成。基线验证 loss：" + str(round(base_loss, 6)) + "；微调后验证 loss：" + str(round(final_loss, 6)) + "；验证 loss 相对改善：" + str(loss_change) + "%；生成样例数：" + str(len(samples)) + "。所有样例都必须人工审核，指标不构成安全认证。")
    write_json(output_dir / "training_status.json", {
        "status": "completed",
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "message": "Training, evaluation, and sample generation completed.",
    })

    if loss_change > 0:
        evaluation = "验证集 loss 在本次小样本上下降，但仍需检查生成质量与过拟合；不能据此宣称模型已具备通用能力或安全性。"
    elif loss_change < 0:
        evaluation = "验证集 loss 上升，本次未显示预测指标改善。应检查学习率、数据质量和训练轮数，并人工审核输出。"
    else:
        evaluation = "验证集 loss 未出现可测量的改善。应检查训练配置、数据和训练目标。"
    summary = (
        "# 本次训练摘要\n\n"
        "## 项目最高原则\n\n"
        "- " + PROJECT_PRINCIPLES[0] + "\n"
        "- " + PROJECT_PRINCIPLES[1] + "\n\n"
        "- 状态：completed\n"
        "- 模型：" + args.model_name + "\n"
        "- GPU：" + str(gpu_name) + "（" + str(gpu_memory_gib) + " GiB）\n"
        "- 训练/验证样本：" + str(len(training_records)) + "/" + str(len(validation_records)) + "\n"
        "- 验证集 loss：基线 " + str(round(base_loss, 6)) + " → 微调后 " + str(round(final_loss, 6)) + "\n"
        "- 验证集 PPL：基线 " + str(safe_ppl(base_loss)) + " → 微调后 " + str(safe_ppl(final_loss)) + "\n"
        "- 验证 loss 相对改善： " + str(loss_change) + "%\n"
        "- 耗时：" + str(duration) + " 秒\n\n"
        "## 评价\n\n" + evaluation + "\n\n"
        "本次语料很小，指标波动可能很大。所有生成样例都需要人工审核，不能把 loss 改善等同于事实可靠性或安全认证。\n"
    )
    (output_dir / "summary.md").write_text(summary, encoding="utf-8")
    logger.info("Final validation loss: %.6f; PPL: %s", final_loss, safe_ppl(final_loss))
    logger.info("Evaluation loss improvement: %.3f%%", loss_change)
    logger.info("Saved adapter and report files to %s", output_dir)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate Chinese GPT-2 with LoRA.")
    parser.add_argument("--model-name", default=MODEL_DEFAULT)
    parser.add_argument("--data", default="data/safety_humanity_train_v2.jsonl")
    parser.add_argument("--eval-data", default="data/safety_humanity_eval_v1.jsonl")
    parser.add_argument("--adapter-path", default=None, help="Path to a previously approved LoRA adapter to continue training from.")
    parser.add_argument("--output-dir", default="training_output")
    parser.add_argument("--seed", type=int, default=SEED_DEFAULT)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--epochs", type=float, default=3)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--eval-batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=2)
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--logging-steps", type=int, default=5)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--require-gpu", action="store_true")
    parser.add_argument("--require-t4", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logger(output_dir)
    try:
        return run(args)
    except Exception as exc:
        logger.exception("Training pipeline failed: %s", exc)
        write_json(output_dir / "training_status.json", {
            "status": "failed",
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        return 1


if __name__ == "__main__":
    raise SystemExit(main())