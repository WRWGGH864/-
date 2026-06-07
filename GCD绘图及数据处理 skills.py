import argparse
import datetime
import logging
import traceback
from io import StringIO
from pathlib import Path

import gcd_utils
import matplotlib.pyplot as plt
from matplotlib import font_manager
import matplotlib
import pandas as pd


logging.basicConfig(
    filename="GCD绘图及数据处理_errors.log",
    level=logging.ERROR,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _configure_matplotlib_font():
    """Try to set a font that supports Chinese characters so titles/labels render correctly.

    Picks the first available font from a preferred list. Ensures minus sign renders.
    """
    preferred = [
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "Noto Sans CJK SC",
        "Noto Sans CJK JP",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in preferred:
        if name in available:
            matplotlib.rcParams["font.sans-serif"] = [name]
            matplotlib.rcParams["axes.unicode_minus"] = False
            return
    matplotlib.rcParams["axes.unicode_minus"] = False


_configure_matplotlib_font()


# Use shared gcd_utils implementations for the processing functions in this script.
read_input_file = gcd_utils.read_input_file
choose_input_files = gcd_utils.choose_input_files
standardize_gcd_columns = gcd_utils.standardize_gcd_columns
validate_gcd_dataframe = gcd_utils.validate_gcd_dataframe
calculate_specific_capacity = gcd_utils.calculate_specific_capacity
infer_gcd_segments = gcd_utils.infer_gcd_segments
compute_coulombic_efficiency = gcd_utils.compute_coulombic_efficiency
summarize_capacity = gcd_utils.summarize_capacity
plot_gcd_curves = gcd_utils.plot_gcd_curves
export_results = gcd_utils.export_results
export_for_origin = gcd_utils.export_for_origin
save_error_log = gcd_utils.save_error_log
generate_sample_gcd_dataframe = gcd_utils.generate_sample_gcd_dataframe


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GCD绘图及数据处理脚本：支持 Excel / CSV / TXT 输入，生成图表与导出数据。"
      )
    parser.add_argument(
        "--input",
        "-i",
        nargs="+",
        help="输入数据文件路径 (.csv, .txt, .xls, .xlsx)，可指定多个文件一起处理",
    )
    parser.add_argument("--sheet", help="Excel 工作表名称或索引（可选）")
    parser.add_argument("--delimiter", help="CSV/TXT 文件分隔符（默认自动识别）")
    parser.add_argument("--mass", type=float, default=2.5, help="样品质量 mg，用于比容量计算")
    parser.add_argument("--output-dir", default="GCD_output", help="结果输出目录")
    parser.add_argument("--skip-export", action="store_true", help="仅生成图形，不导出Excel/CSV")
    parser.add_argument("--skip-origin", action="store_true", help="不生成Origin导入文件")
    parser.add_argument("--dialog", action="store_true", help="弹出文件选择对话框选择一个或多个输入文件")
    parser.add_argument("--current-density", help="测试电流密度，例如 0.1 A/g")
    parser.add_argument("--voltage-window", help="电压窗口，例如 0.01-3.0")
    parser.add_argument("--sample", action="store_true", help="使用示例合成数据，而不是读取输入文件")
    args = parser.parse_args()

    try:
        if args.sample:
            df = generate_sample_gcd_dataframe()
            df["Dataset"] = "Sample"
            print("使用示例合成数据进行演示。")
            dataset_dfs = [df]
            summary_rows = [
                {"Dataset": "Sample", "current_density": args.current_density, "voltage_window": args.voltage_window, **summarize_capacity(df)}
            ]
        else:
            if args.dialog or not args.input:
                print("正在打开文件选择窗口，请在弹出的窗口中选择一个或多个数据文件...")
                args.input = choose_input_files()
                print("已选择文件：", args.input)

            if not args.input:
                parser.error("必须指定 --input 文件路径，或使用 --dialog 弹出文件选择对话框，或使用 --sample 来生成示例数据。")

            dataset_dfs = []
            summary_rows = []
            for input_path in args.input:
                df = read_input_file(input_path, sheet_name=args.sheet, delimiter=args.delimiter)
                print(f"已读取输入文件: {input_path}")
                print(f"原始列名: {list(df.columns)}")
                df = standardize_gcd_columns(df)
                print("已标准化列名：", df.columns.tolist())
                validated_df = validate_gcd_dataframe(df)
                print(f"{input_path} 数据验证通过，数据行数：{len(validated_df)}")
                capacity_df = calculate_specific_capacity(validated_df, mass_mg=args.mass)
                capacity_df = infer_gcd_segments(capacity_df)
                label = Path(input_path).stem
                capacity_df["Dataset"] = label
                dataset_dfs.append(capacity_df)
                summary = {
                    "Dataset": label,
                    "current_density": args.current_density,
                    "voltage_window": args.voltage_window,
                    **summarize_capacity(capacity_df),
                    **compute_coulombic_efficiency(capacity_df),
                }
                summary_rows.append(summary)

        combined_df = pd.concat(dataset_dfs, ignore_index=True)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        plot_path = output_dir / "gcd_curves.png"
        plot_gcd_curves(combined_df, str(plot_path))

        if not args.skip_export:
            export_results(combined_df, output_dir)
            pd.DataFrame(summary_rows).to_csv(output_dir / "summary_results.csv", index=False)
            print("已导出多数据集摘要 summary_results.csv")

        if not args.skip_origin:
            export_for_origin(combined_df, output_dir)

        print("处理完成，结果摘要：")
        for row in summary_rows:
            summary_line = (
                f"  {row['Dataset']}: mean={row['mean_specific_capacity']:.3f}, "
                f"max={row['max_specific_capacity']:.3f}, "
                f"min={row['min_specific_capacity']:.3f}, "
                f"count={row['cycle_count']}"
            )
            if row.get("current_density"):
                summary_line += f", current_density={row['current_density']}"
            if row.get("voltage_window"):
                summary_line += f", voltage_window={row['voltage_window']}"
            if row.get("coulombic_efficiency_pct") is not None:
                summary_line += f", coulombic_efficiency={row['coulombic_efficiency_pct']:.2f}%"
            print(summary_line)

        print(f"所有输出已保存至：{output_dir.resolve()}")

    except Exception as exc:
        print("发生错误，请检查日志: GCD绘图及数据处理_errors.log")
        save_error_log("main", exc)
        raise


if __name__ == "__main__":
    main()
