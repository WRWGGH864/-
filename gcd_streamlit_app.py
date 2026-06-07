import tempfile
from pathlib import Path
from uuid import uuid4

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from gcd_utils import (
    build_gcd_summary,
    plot_gcd_curves,
    process_gcd_file,
)


def _configure_matplotlib_font():
    preferred = [
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "Noto Sans CJK SC",
        "Noto Sans CJK JP",
    ]
    from matplotlib import font_manager

    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in preferred:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            plt.rcParams["axes.unicode_minus"] = False
            return
    plt.rcParams["axes.unicode_minus"] = False


_configure_matplotlib_font()


def save_uploaded_file(uploaded_file):
    tmp_dir = Path(tempfile.gettempdir())
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dst = tmp_dir / f"{uuid4().hex}_{uploaded_file.name}"
    with open(dst, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(dst)


@st.cache_data(show_spinner=False)
def process_file(path: str, mass_mg: float, current_density: str, voltage_window: str):
    label = Path(path).stem
    capacity_df = process_gcd_file(path, mass_mg=mass_mg, label=label)
    summary = build_gcd_summary(capacity_df, current_density, voltage_window)
    return capacity_df, summary


def main():
    st.set_page_config(page_title="GCD 绘图与数据处理", layout="wide")
    st.title("GCD 绘图与数据处理 Web App")
    st.markdown(
        "上传你的 GCD 数据文件，脚本将自动识别列名，计算比容量并绘制比容量-电压曲线。"
    )

    with st.sidebar:
        st.header("参数设置")
        mass_mg = st.number_input("样品质量 (mg)", value=2.5, min_value=0.01, step=0.1)
        current_density = st.text_input("测试电流密度", value="0.1 A/g")
        voltage_window = st.text_input("电压窗口", value="0.01-3.0")
        st.markdown("---")
        uploaded_files = st.file_uploader(
            "上传一个或多个数据文件",
            type=["csv", "txt", "xls", "xlsx", "xlsm", "xlsb"],
            accept_multiple_files=True,
        )
        st.info("上传文件后会自动处理，生成图表与摘要结果。")

    if not uploaded_files:
        st.info("请在左侧上传数据文件后，页面会自动处理。")
        return

    results = []
    summaries = []

    for uploaded_file in uploaded_files:
        file_path = save_uploaded_file(uploaded_file)
        try:
            capacity_df, summary = process_file(file_path, mass_mg, current_density, voltage_window)
            st.subheader(f"文件：{uploaded_file.name}")
            st.write("已识别并处理的列：", list(capacity_df.columns))
            with st.expander("查看前 20 行数据", expanded=False):
                st.dataframe(capacity_df.head(20))

            fig = plot_gcd_curves(capacity_df, output_path=None)
            st.pyplot(fig)
            plt.close(fig)

            csv_bytes = capacity_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="下载处理后的 CSV",
                data=csv_bytes,
                file_name=f"{Path(uploaded_file.name).stem}_processed.csv",
                mime="text/csv",
            )

            summaries.append(summary)
            results.append(capacity_df)
        except Exception as exc:
            st.error(f"处理文件 {uploaded_file.name} 时出错：{exc}")

    if results:
        if len(results) > 1:
            combined_df = pd.concat(results, ignore_index=True)
            st.markdown("---")
            st.subheader("合并比容量曲线")
            combined_fig = plot_gcd_curves(combined_df, output_path=None)
            st.pyplot(combined_fig)
            plt.close(combined_fig)

            combined_csv = combined_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="下载合并数据 CSV",
                data=combined_csv,
                file_name="gcd_combined_processed.csv",
                mime="text/csv",
            )

        st.markdown("---")
        st.subheader("摘要结果")
        summary_df = pd.DataFrame(summaries)
        st.dataframe(summary_df)
        st.download_button(
            label="下载摘要结果 CSV",
            data=summary_df.to_csv(index=False).encode("utf-8"),
            file_name="summary_results.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
