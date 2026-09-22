"""M5 提交物生成：模型卡（.inc+.json）+ 日志包 + Schema 校验

提交物布局（submission/，git 追踪，重跑覆盖——最新即提交态，历史看 git）：
  submission/<dev>_modelcard.inc   —— ngspice .model 行（可直接 pre_osdi 加载）
  submission/<dev>_modelcard.json  —— 参数+元数据+逐形态 NRMSE+预算审计
  submission/manifest.json         —— 清单 + 各器件 Schema 校验结果
  submission/logs/                 —— 各器件最新运行日志（可审计证据包）

Schema 校验四项（validate_card）：
  ① 必填字段齐全（device/model/params/space/nrmse/qa_pass）；
  ② 参数名 ∈ 已知集合（QA_RULES 键——卡07 以来提取空间的全部参数）；
  ③ 参数值 ∈ QA 物理范围（任务卡10-bis 定稿规则）；
  ④ 逐形态 NRMSE ≤ 分形态达标线（FORM_TARGET）；qa_pass 必须为真。

用法：
  python src/pipeline/make_submission.py            # 从最新 run 日志重建（离线模式）
  或被 run_agent.py --devices 多器件跑完后自动调用（内存模式）。
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.agent.main_graph import FORM_TARGET  # noqa: E402
from src.agent.qa_loop import QA_RULES  # noqa: E402
from src.tools.interface import MODEL_SWITCHES  # noqa: E402

SUB_DIR = ROOT / "submission"
REQUIRED = ["device", "model", "params", "space", "nrmse", "qa_pass"]


def _git_head() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           cwd=ROOT, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or "unknown"
    except Exception:                                # noqa: BLE001
        return "unknown"


def _inc_text(dev: str, card: dict) -> str:
    sw = " ".join(f"{k}={v}" for k, v in MODEL_SWITCHES.items())
    params = " ".join(f"{p}={float(v):.10g}" for p, v in card["params"].items())
    return (f"* GaN HEMT ASM-HEMT 提取模型卡（run_agent 自动生成，{dev}）\n"
            f"* 逐形态 NRMSE: {card.get('rmse_per_form')}\n"
            f".model {dev}_asmhemt asmhemt ({sw} {params})\n")


def validate_card(card: dict) -> tuple:
    """Schema 校验：返回 (errors, warnings)。
    errors=硬项（必填字段/参数名枚举/QA 物理范围/qa_pass）——不过即拒收；
    warnings=软项（NRMSE 超达标线）——熔断 B 保底解允许带 warning 交卷
    （作战手册够用原则：QA 乘性因子保住，NRMSE 评分项打折，卡13 量化依据）。"""
    errors = [f"缺必填字段 {k}" for k in REQUIRED if k not in card]
    if errors:
        return errors, []
    for p in card["params"]:
        if p not in QA_RULES:
            errors.append(f"参数 {p} 不在已知集合 {sorted(QA_RULES)}")
    for p, v in card["params"].items():
        lo, hi = QA_RULES.get(p, (-float("inf"), float("inf")))
        if not (lo <= v <= hi):
            errors.append(f"{p}={v:.4g} 超出物理范围 [{lo:.4g}, {hi:.4g}]")
    if not card.get("qa_pass"):
        errors.append("qa_pass=False")
    warnings = []
    per = card.get("rmse_per_form") or {}
    if per:
        for f, r in per.items():
            t = FORM_TARGET.get(f, 0.01)
            if r > t:
                warnings.append(f"形态 {f} NRMSE={r:.3%} 超达标线 {t:.1%}（熔断 B 软项）")
    elif not (0 <= (card.get("nrmse") or 9) < 0.01):
        warnings.append(f"NRMSE={card.get('nrmse')} 超 1%（无逐形态明细，熔断 B 软项）")
    return errors, warnings


def build_submission(results: dict) -> tuple:
    """results: {device: final_state}。返回 (输出目录 Path, 违规列表)。"""
    logs_dst = SUB_DIR / "logs"
    logs_dst.mkdir(parents=True, exist_ok=True)
    head = _git_head()
    manifest = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "git_head": head, "devices": {}, "schema_ok": True}
    problems = []
    for dev, final in results.items():
        card = dict(final["final_card"])
        card["git_head"] = head
        card["budget"] = {k: v for k, v in final["budget"].items() if k != "t0"}
        errors, warnings = validate_card(card)
        manifest["devices"][dev] = {
            "card": f"{dev}_modelcard.json", "inc": f"{dev}_modelcard.inc",
            "schema_ok": not errors, "errors": errors, "warnings": warnings,
            "rmse_per_form": card.get("rmse_per_form"),
            "sim_count": card["budget"].get("sim_count"),
            "llm_calls": card["budget"].get("llm_calls")}
        (SUB_DIR / f"{dev}_modelcard.json").write_text(
            json.dumps(card, ensure_ascii=False, default=str, indent=1), encoding="utf-8")
        (SUB_DIR / f"{dev}_modelcard.inc").write_text(_inc_text(dev, card), encoding="utf-8")
        if errors:
            manifest["schema_ok"] = False
            problems += [f"{dev}: {b}" for b in errors]
        for w in warnings:
            print(f"  ⚠️ {dev}: {w}")
    for dev in results:                              # 日志包：各器件最新 run json
        runs = [p for p in sorted((ROOT / "logs").glob(f"run_{dev}_*.json"))
                if not p.name.endswith(".prev")]
        if runs:
            shutil.copy(runs[-1], logs_dst / runs[-1].name)
    (SUB_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return SUB_DIR, problems


def _from_latest_logs(devices: list) -> dict:
    """离线模式：从 logs/ 最新 run json 重建 results（不重跑仿真）。"""
    results = {}
    for dev in devices:
        runs = [p for p in sorted((ROOT / "logs").glob(f"run_{dev}_*.json"))
                if not p.name.endswith(".prev")]
        if not runs:
            sys.exit(f"{dev}: 无运行日志，无法离线生成提交物")
        d = json.loads(runs[-1].read_text(encoding="utf-8"))
        results[dev] = {"final_card": d["final_card"], "budget": d["budget"]}
    return results


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--devices", default="jia,yi")
    a = ap.parse_args()
    devs = [d.strip() for d in a.devices.split(",") if d.strip()]
    out, probs = build_submission(_from_latest_logs(devs))
    print(f"提交物已生成：{out}")
    if probs:
        print("Schema 校验 ❌：")
        for b in probs:
            print(f"  - {b}")
        sys.exit(1)
    print("Schema 校验 ✅ 全部通过")
