#!/usr/bin/env python3
"""Turn collected Kaggle outputs into an honest, auditable run report."""
import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def fmt(value, digits=5):
    if value is None:
        return "不可用"
    if isinstance(value, float):
        return str(round(value, digits))
    return str(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    output_dir = run_dir / "kaggle_output"
    status_file = run_dir / "status.txt"
    status = status_file.read_text(encoding="utf-8").strip().splitlines()[0] if status_file.exists() else "UNKNOWN"

    copied = {}
    stage_files = []
    for filename in [
        "training.log", "metrics.json", "samples.json", "run_metadata.json",
        "summary.md", "training_status.json",
    ]:
        matches = list(output_dir.rglob(filename)) if output_dir.exists() else []
        if matches:
            target = run_dir / filename
            if matches[0].resolve() != target.resolve():
                shutil.copy2(matches[0], target)
            copied[filename] = target

    stage_dirs = list(output_dir.rglob("stages")) if output_dir.exists() else []
    for source_stage_dir in stage_dirs:
        for source_stage in sorted(source_stage_dir.glob("*.md")):
            target_stage_dir = run_dir / "stages"
            target_stage_dir.mkdir(parents=True, exist_ok=True)
            target_stage = target_stage_dir / source_stage.name
            shutil.copy2(source_stage, target_stage)
            stage_files.append(target_stage.name)

    training_status = read_json(run_dir / "training_status.json") if (run_dir / "training_status.json").exists() else {}
    metrics = read_json(run_dir / "metrics.json") if (run_dir / "metrics.json").exists() else {}
    metadata = read_json(run_dir / "run_metadata.json") if (run_dir / "run_metadata.json").exists() else {}
    samples = read_json(run_dir / "samples.json") if (run_dir / "samples.json").exists() else []

    if status == "BLOCKED_MISSING_KAGGLE_SECRETS":
        final_status = "BLOCKED_MISSING_KAGGLE_SECRETS"
    elif status in ("KAGGLE_PUSH_FAILED", "TIMEOUT", "KAGGLE_STATUS_FAILED", "KAGGLE_OUTPUT_UNAVAILABLE"):
        final_status = status
    elif training_status.get("status") == "failed":
        final_status = "TRAINING_FAILED"
    elif status == "COMPLETE" and training_status.get("status") == "completed" and metrics:
        final_status = "SUCCESS"
    elif status == "COMPLETE":
        final_status = "INCOMPLETE_OUTPUTS"
    else:
        final_status = status or "UNKNOWN"

    report = []
    report.append("# 每日 GPT-2 训练运行报告")
    report.append("")
    report.append("- 生成时间（UTC）： " + datetime.now(timezone.utc).isoformat())
    report.append("- 运行目录： " + str(run_dir))
    repository = os.environ.get("GITHUB_REPOSITORY", "mjw3177109/damoxingtest")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if run_id:
        report.append("- GitHub Actions 运行记录： https://github.com/" + repository + "/actions/runs/" + run_id)
        report.append("- 模型与完整输出 Artifact： https://github.com/" + repository + "/actions/runs/" + run_id + "/artifacts")
    report.append("- Kaggle 任务状态： " + status)
    report.append("- 最终判定： **" + final_status + "**")
    report.append("")
    report.append("## 本次结果")
    report.append("")
    if metrics:
        report.extend([
            "- 基础模型： " + str(metrics.get("model_name", metadata.get("model_name", "未知"))),
            "- GPU： " + str(metrics.get("gpu_name", metadata.get("gpu_name", "未知"))),
            "- 显存（GiB）： " + fmt(metrics.get("gpu_memory_gib", metadata.get("gpu_memory_gib"))),
            "- 训练样本： " + fmt(metrics.get("train_examples")),
            "- 验证样本： " + fmt(metrics.get("validation_examples")),
            "- 基线验证 loss： " + fmt(metrics.get("base_eval_loss")),
            "- 微调后验证 loss： " + fmt(metrics.get("final_eval_loss")),
            "- 基线 PPL： " + fmt(metrics.get("base_eval_ppl")),
            "- 微调后 PPL： " + fmt(metrics.get("final_eval_ppl")),
            "- 验证 loss 相对改善（%）： " + fmt(metrics.get("eval_loss_improvement_pct")),
            "- 训练耗时（秒）： " + fmt(metrics.get("train_runtime_seconds")),
            "",
        ])
        change = metrics.get("eval_loss_improvement_pct")
        if isinstance(change, (int, float)) and change > 0:
            report.append("## 整体评价")
            report.append("")
            report.append("本次验证集 loss 在当前小规模保留集上下降，说明该指标有改善迹象。由于语料和验证集规模很小，这不是通用能力提升或安全性的证明；仍需审查生成样例、过拟合和数据质量。")
        elif isinstance(change, (int, float)) and change < 0:
            report.append("## 整体评价")
            report.append("")
            report.append("本次验证集 loss 上升，当前结果不支持“微调改善了预测表现”的结论。应检查学习率、训练轮数、样本质量和数据切分，并人工审核输出。")
        else:
            report.append("## 整体评价")
            report.append("")
            report.append("当前指标没有显示明确的验证集 loss 改善。需要结合训练日志、生成样例和后续更可靠的测试集继续判断。")
    else:
        report.append("没有找到有效的 metrics.json，因此不能声称本次模型训练和评估成功。")
        if training_status.get("error"):
            report.append("")
            report.append("训练错误类型： " + str(training_status.get("error_type", "未知")))
            report.append("")
            report.append("错误摘要： " + str(training_status.get("error")))
        report.append("")
        report.append("## 整体评价")
        report.append("")
        report.append("本次运行没有足够的实测指标支持模型质量结论。请先解决凭据、GPU、配额、网络或训练脚本问题，再重新运行。")

    report.append("")
    report.append("## 阶段记录")
    report.append("")
    if stage_files:
        for stage_name in sorted(set(stage_files)):
            report.append("- stages/" + stage_name)
    else:
        report.append("没有找到已完成阶段的独立说明文件。")
    report.append("")
    report.append("## 模型输出与日志")
    report.append("")
    if "samples.json" in copied and isinstance(samples, list):
        report.append("- 已保存生成样例： samples.json（" + str(len(samples)) + " 条）")
    else:
        report.append("- 没有找到 samples.json。")
    for name in ["training.log", "metrics.json", "run_metadata.json", "training_status.json", "summary.md"]:
        if name in copied:
            report.append("- 已保存： " + name)
    report.append("")
    report.append("## 安全与质量边界")
    report.append("")
    report.append("- 自动生成的回答都需要人工审核；本报告不是安全认证。")
    report.append("- 小数据集上的 loss 和 PPL 不能证明事实准确性、通用推理能力或价值观稳定性。")
    report.append("- 不将失败、超时、未配置凭据或缺失指标描述为成功。")
    report.append("- 本项目原则仍为：保护用户；维护人类。")
    report.append("")
    report.append("## 下一步计划")
    report.append("")
    if final_status == "SUCCESS":
        report.append("1. 人工复核 samples.json，检查事实性、隐私、伤害风险、偏见和是否遵循指令。")
        report.append("2. 比较验证集指标与上一版本，不因单次 loss 变化就直接宣称模型进步。")
        report.append("3. 逐步扩充有明确许可、经过清洗和审阅的数据，并建立固定测试集。")
    else:
        report.append("1. 根据 status.txt、Kaggle 日志和训练日志定位阻塞原因。")
        report.append("2. 修复凭据、GPU 配额、网络或训练问题后，再进行新的真实运行。")
        report.append("3. 只有指标文件、样例输出和报告齐全时才判定训练成功。")

    (run_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (run_dir / "final_status.txt").write_text(final_status + "\n", encoding="utf-8")
    print("Final report written. Status: " + final_status)


if __name__ == "__main__":
    main()