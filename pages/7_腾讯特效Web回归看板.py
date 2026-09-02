"""Read-only E2 dashboard for the Tencent Effect Web candidate.

The page displays the generated contract regression report only.  It does not
load credentials, open a browser, call Tencent, or promote the Provider Card.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "reports/tencent_effect_web_regression_v1.json"


def _load_report() -> dict[str, Any] | None:
    if not REPORT_PATH.is_file():
        return None
    try:
        value = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def main() -> None:
    st.set_page_config(page_title="腾讯特效 Web 回归看板", page_icon="🧪")
    st.title("腾讯特效 Web｜E2 回归看板")
    st.caption(
        "这张看板展示的是 B 方案结果回传合同的多样本、异常拦截和批量隔离证据。"
        "它不是腾讯视觉效果评分，也不会把 candidate 自动升级。"
    )
    report = _load_report()
    if report is None:
        st.info("尚未生成回归报告；运行 scripts/run_effect_web_regression.py 后刷新。")
        return

    metrics = st.columns(6)
    metrics[0].metric("样本数", report.get("total", "—"))
    metrics[1].metric("通过", report.get("passed", "—"))
    metrics[2].metric("失败", report.get("failed", "—"))
    metrics[3].metric("拦截样本", report.get("rejected_cases", "—"))
    metrics[4].metric(
        "批量隔离",
        "PASS" if report.get("batch_failure_isolation_passed") else "FAIL",
    )
    metrics[5].metric("硬安全", "PASS" if report.get("hard_safety_passed") else "FAIL")

    st.info(
        "结果图只在回归脚本单次运行的内存中解码；报告保存的是样本类别、观测状态、错误代码和 Trace，"
        "不保存图片 bytes 或 data URL。"
    )
    items = report.get("items", [])
    if isinstance(items, list):
        rows = [
            {
                "案例": item.get("case_id"),
                "类型": item.get("category"),
                "预期": item.get("expected"),
                "实际": item.get("observed"),
                "结果": "PASS" if item.get("passed") else "FAIL",
                "异常代码": item.get("anomaly_code") or "—",
                "结果字节（仅运行时）": item.get("output_bytes_seen", 0),
            }
            for item in items
            if isinstance(item, dict)
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        for item in items:
            if not isinstance(item, dict):
                continue
            with st.expander(f"{item.get('case_id')}｜Trace", expanded=False):
                st.json(item.get("trace", []))

    st.download_button(
        "下载脱敏回归 JSON",
        data=REPORT_PATH.read_bytes(),
        file_name=REPORT_PATH.name,
        mime="application/json",
    )
    st.warning(
        "当前报告是合同/异常回归 PASS，不是多样本真实视觉效果 PASS；"
        "E3 promotion 仍需要真实 Web 回执、"
        "供应商隐私/区域/费用证据和产品负责人批准。"
    )


if __name__ == "__main__":
    main()
