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
        matches.sort(key=lambda p: (0 if "training_output" in p.parts else 1, len(p.parts)))
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
    quality_gate = read_json(run_dir / "quality_gate.json") if (run_dir / "quality_gate.json").exists() else {}
    metrics = read_json(run_dir / "metrics.json") if (run_dir / "metrics.json").exists() else {}
    metadata = read_json(run_dir / "run_metadata.json") if (run_dir / "run_metadata.json").exists() else {}
    samples = read_json(run_dir / "samples.json") if (run_dir / "samples.json").exists() else []
    skipped = bool(training_status.get("skipped_no_changes"))
    if skipped:
        # Reused historical stage files must not masquerade as stages executed now.
        for stage_file in (run_dir / "stages").glob("*.md"):
            stage_file.unlink()
        stage_files.clear()

    if status == "BLOCKED_MISSING_KAGGLE_SECRETS":
        final_status = "BLOCKED_MISSING_KAGGLE_SECRETS"
    elif status in ("KAGGLE_PUSH_FAILED", "TIMEOUT", "KAGGLE_STATUS_FAILED", "KAGGLE_OUTPUT_UNAVAILABLE"):
        final_status = status
    elif training_status.get("status") == "failed":
        final_status = "TRAINING_FAILED"
    elif training_status.get("skipped_no_changes"):
        final_status = "SKIPPED_NO_CHANGES"
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
    if final_status == "BLOCKED_SAME_DATA_RETRAIN_REQUIRES_APPROVAL":
        report.append("- 本次训练动作：安全阻断；未提交 Kaggle Kernel，未执行 GPU 训练或评估。")
        report.append("- 阻断原因：相同训练和验证数据存在历史完成记录，但当前配方或配置不满足精确复用条件。")
    if training_status.get("skipped_no_changes"):
        report.append("- 本次训练动作：跳过重复训练；复用已有指标与样例，未进行新的 GPU 参数更新。")
        report.append("- 复用来源： " + str(training_status.get("reused_from_run", "历史成功运行")))
    report.append("")
    report.append("## 历史复用指标（本轮未训练或重新评估）" if skipped else "## 本次结果")
    report.append("")
    if metrics:
        if skipped:
            report.append("- 指标来源： " + str(training_status.get("reused_from_run", "历史运行")) + "；以下指标不是本次新测量。")
        report.extend([
            "- 基础模型： " + str(metrics.get("model_name", metadata.get("model_name", "未知"))),
            "- GPU： " + ("本轮未使用；历史来源：" + str(metadata.get("source_run_gpu_name", "未知")) if skipped else str(metrics.get("gpu_name", metadata.get("gpu_name", "未知")))),
            "- 显存（GiB）： " + (("本轮未使用；历史来源：" + fmt(metadata.get("source_run_gpu_memory_gib"))) if skipped else fmt(metrics.get("gpu_memory_gib", metadata.get("gpu_memory_gib")))),
            "- 训练样本： " + fmt(metrics.get("train_examples")),
            "- 验证样本： " + fmt(metrics.get("validation_examples")),
            "- 基线验证 loss： " + fmt(metrics.get("base_eval_loss")),
            "- 微调后验证 loss： " + fmt(metrics.get("final_eval_loss")),
            "- 基线 PPL： " + fmt(metrics.get("base_eval_ppl")),
            "- 微调后 PPL： " + fmt(metrics.get("final_eval_ppl")),
            "- 验证 loss 相对改善（%）： " + fmt(metrics.get("eval_loss_improvement_pct")),
            ("- 历史训练耗时（秒）： " if skipped else "- 训练耗时（秒）： ") + fmt(metrics.get("train_runtime_seconds")),
            "",
        ])
        change = metrics.get("eval_loss_improvement_pct")
        if skipped:
            report.append("## 整体评价")
            report.append("")
            report.append("本次未进行新的训练或评估；以上 Loss、PPL 和生成样例均为历史证据，不得视为本轮改进。")
        elif isinstance(change, (int, float)) and change > 0:
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
    report.append("## 候选模型晋级门槛")
    report.append("")
    if quality_gate:
        report.append("- 自动晋级： " + ("已通过初步门槛" if quality_gate.get("promotion_approved") else "未通过；保留上一个已批准版本"))
        report.append("- 有效生成样例： " + str(quality_gate.get("meaningful_generation_samples", 0)) + "/" + str(quality_gate.get("generation_sample_count", 0)))
        for reason in quality_gate.get("reasons", []):
            report.append("- 未通过原因： " + str(reason))
        report.append("- 自动门槛仅为初筛，不等于人工安全认证。")
    else:
        report.append("本次未生成 quality_gate.json；没有证据表明候选模型通过晋级检查。")
    report.append("")
    report.append("## 阶段记录" if not skipped else "## 本轮阶段记录（未执行训练）")
    report.append("")
    if skipped:
        report.append("本次未执行训练阶段；历史阶段说明仅保留在来源归档中，不属于本轮成果。")
    elif stage_files:
        for stage_name in sorted(set(stage_files)):
            report.append("- stages/" + stage_name)
    else:
        report.append("没有找到已完成阶段的独立说明文件。")
    report.append("")
    report.append("## 模型输出与日志")
    report.append("")
    if "samples.json" in copied and isinstance(samples, list):
        report.append(("- 已保存历史复用生成样例： " if skipped else "- 已保存生成样例： ") + "samples.json（" + str(len(samples)) + " 条）")
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
    if final_status == "SKIPPED_NO_CHANGES":
        report.append("本次训练集、评估集和训练方案与最近一次完整运行一致，因此跳过重复 GPU 训练。新增数据或训练方案发生变化后再启动新训练。")
    elif final_status == "BLOCKED_SAME_DATA_RETRAIN_REQUIRES_APPROVAL":
        report.append("1. 核对历史 Run 的数据哈希、训练配置、代码 SHA 与模型质量，不要将配方哈希变化直接视为必须重训。")
        report.append("2. 确需同数据重训时，仅通过 workflow_dispatch 的 approve_same_data_retrain 明确审批；默认保持阻断。")
        report.append("3. 审批后仍须检查 Kaggle Kernel 状态、并发和 GPU 配额，不能把审批或 Actions success 当作训练成功。")
    elif final_status == "SUCCESS":
        report.append("1. 人工复核 samples.json，检查事实性、隐私、伤害风险、偏见和是否遵循指令。")
        report.append("2. 比较验证集指标与上一版本，不因单次 loss 变化就直接宣称模型进步。")
        report.append("3. 逐步扩充有明确许可、经过清洗和审阅的数据，并建立固定测试集。")
        if quality_gate and not quality_gate.get("promotion_approved"):
            report.append("4. 候选 Adapter 未通过自动质量门槛；保留上一个已批准版本，不自动晋级。")
    else:
        report.append("1. 根据 status.txt、Kaggle 日志和训练日志定位阻塞原因。")
        report.append("2. 修复凭据、GPU 配额、网络或训练问题后，再进行新的真实运行。")
        report.append("3. 只有指标文件、样例输出和报告齐全时才判定训练成功。")

    (run_dir / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (run_dir / "final_status.txt").write_text(final_status + "\n", encoding="utf-8")
    print("Final report written. Status: " + final_status)


if __name__ == "__main__":
    main()