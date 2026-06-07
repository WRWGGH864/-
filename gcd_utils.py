import traceback
from io import StringIO
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd


def _normalize_column_name(name: str) -> str:
    token = str(name).strip().lower()
    token = token.replace("\ufeff", "").replace("\u00a0", " ").replace("\u3000", " ")
    token = token.replace("(", " ").replace(")", " ").replace("%", "").replace("/", " ")
    token = token.replace("-", " ").replace("_", " ").replace(".", " ")
    token = " ".join(token.split())
    return token


def read_input_file(path: str, sheet_name=None, delimiter=None) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"输入文件未找到: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(file_path, delimiter=delimiter or ",", encoding="utf-8-sig")
        if df.shape[1] == 1 and "," in df.columns[0]:
            lines = file_path.read_text(encoding="utf-8-sig").splitlines()
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('"') and stripped.endswith('"'):
                    stripped = stripped[1:-1]
                cleaned_lines.append(stripped)
            repaired = StringIO("\n".join(cleaned_lines))
            return pd.read_csv(repaired, delimiter=delimiter or ",", encoding="utf-8-sig")
        return df
    if suffix == ".txt":
        if delimiter:
            return pd.read_csv(file_path, delimiter=delimiter, encoding="utf-8-sig")
        try:
            return pd.read_csv(file_path, encoding="utf-8-sig")
        except Exception:
            return pd.read_csv(file_path, delimiter="\t", encoding="utf-8-sig")
    if suffix in {".xls", ".xlsx", ".xlsm", ".xlsb"}:
        result = pd.read_excel(file_path, sheet_name=sheet_name)
        if isinstance(result, dict):
            if len(result) == 1:
                result = next(iter(result.values()))
            else:
                raise ValueError(
                    f"Excel 文件包含多个工作表，请使用 --sheet 指定要读取的工作表。可选工作表：{list(result.keys())}"
                )
        if result.shape[1] == 1:
            first_col = result.columns[0]
            if isinstance(first_col, str) and "," in first_col:
                lines = [str(first_col)] + [str(x) for x in result.iloc[:, 0].tolist()]
                cleaned_lines = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith('"') and stripped.endswith('"'):
                        stripped = stripped[1:-1]
                    cleaned_lines.append(stripped)
                repaired = StringIO("\n".join(cleaned_lines))
                return pd.read_csv(repaired, delimiter=delimiter or ",", encoding="utf-8-sig")
        return result

    raise ValueError(
        "仅支持的数据格式为: .csv, .txt, .xls, .xlsx, .xlsm, .xlsb"
    )


def choose_input_files():
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError as exc:
        raise RuntimeError("未安装 tkinter，无法使用文件选择对话框") from exc

    root = tk.Tk()
    root.withdraw()
    root.update()
    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()
    file_paths = filedialog.askopenfilenames(
        parent=root,
        title="选择一个或多个 GCD 数据文件",
        filetypes=[
            ("GCD data files", "*.csv *.txt *.xls *.xlsx *.xlsm *.xlsb"),
            ("CSV files", "*.csv"),
            ("Text files", "*.txt"),
            ("Excel files", "*.xls *.xlsx *.xlsm *.xlsb"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()
    if not file_paths:
        raise RuntimeError("未选择任何文件")
    return list(file_paths)


def standardize_gcd_columns(df: pd.DataFrame) -> pd.DataFrame:
    if not hasattr(df, "columns"):
        raise TypeError(
            "standardize_gcd_columns 期望一个 pandas.DataFrame，实际收到: {}".format(type(df))
        )

    column_mapping = {
        "cycle": "Cycle",
        "cycle number": "Cycle",
        "charge capacity": "Charge Capacity (mAh/g)",
        "charge capacity mah g": "Charge Capacity (mAh/g)",
        "discharge capacity": "Discharge Capacity (mAh/g)",
        "discharge capacity mah g": "Discharge Capacity (mAh/g)",
        "specific capacity": "Specific Capacity (mAh/g)",
        "specific capacity mah g": "Specific Capacity (mAh/g)",
        "specific capacity mahg": "Specific Capacity (mAh/g)",
        "capacity": "Specific Capacity (mAh/g)",
        "voltage": "Voltage (V)",
        "voltage v": "Voltage (V)",
        "voltage(v)": "Voltage (V)",
        "current": "Current (A)",
        "current ma": "Current (A)",
        "current (ma)": "Current (A)",
        "current (a)": "Current (A)",
        "i": "Current (A)",
        "i a": "Current (A)",
        "time": "Time (s)",
        "time s": "Time (s)",
        "time(s)": "Time (s)",
        "time/s": "Time (s)",
        "时间": "Time (s)",
        "时间 s": "Time (s)",
        "时间(s)": "Time (s)",
        "时间/s": "Time (s)",
        "电压": "Voltage (V)",
        "电压 v": "Voltage (V)",
        "电压(v)": "Voltage (V)",
        "电流": "Current (A)",
        "电流 ma": "Current (A)",
        "电流 (ma)": "Current (A)",
        "电流(a)": "Current (A)",
        "充电容量": "Charge Capacity (mAh/g)",
        "放电容量": "Discharge Capacity (mAh/g)",
        "充电 容量": "Charge Capacity (mAh/g)",
        "放电 容量": "Discharge Capacity (mAh/g)",
    }

    fuzzy_rules = [
        ("Charge Capacity (mAh/g)", ["charge capacity", "chargecapacity"]),
        ("Discharge Capacity (mAh/g)", ["discharge capacity", "dischargecapacity"]),
        (
            "Specific Capacity (mAh/g)",
            [
                "specific capacity",
                "specificcapacity",
                "specific capacity mahg",
                "specificcapacitymahg",
                "capacity",
            ],
        ),
        ("Voltage (V)", ["voltage"]),
        ("Current (A)", ["current", "i"]),
        ("Time (s)", ["time"]),
    ]

    new_columns = {}
    current_in_ma = False
    for original in df.columns:
        normalized = _normalize_column_name(str(original))
        compact = normalized.replace(" ", "")
        mapped = column_mapping.get(normalized)
        if mapped is None:
            for target, patterns in fuzzy_rules:
                for pattern in patterns:
                    if pattern in normalized or pattern in compact:
                        mapped = target
                        break
                if mapped:
                    break
        mapped = mapped or original
        new_columns[original] = mapped
        if mapped == "Current (A)" and "ma" in normalized:
            current_in_ma = True

    standardized_df = df.rename(columns=new_columns)
    if current_in_ma and "Current (A)" in standardized_df.columns:
        standardized_df["Current (A)"] = pd.to_numeric(
            standardized_df["Current (A)"], errors="coerce"
        ) / 1000
    return standardized_df


def validate_gcd_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    validated_df = df.copy()
    raw_required = ["Voltage (V)", "Current (A)", "Time (s)"]
    has_raw_data = all(col in validated_df.columns for col in raw_required)
    has_capacity_data = (
        "Charge Capacity (mAh/g)" in validated_df.columns
        or "Discharge Capacity (mAh/g)" in validated_df.columns
        or "Specific Capacity (mAh/g)" in validated_df.columns
    )

    if not has_raw_data and not has_capacity_data:
        normalized_columns = [_normalize_column_name(col) for col in validated_df.columns]
        raise ValueError(
            "缺少必要列: 需要 Voltage, Current, Time 或 Charge/Discharge/Specific Capacity 等列，"
            f"当前读取到列: {list(validated_df.columns)}，"
            f"标准化后列: {normalized_columns}"
        )

    for col in raw_required:
        if col in validated_df.columns:
            validated_df[col] = pd.to_numeric(validated_df[col], errors="coerce")

    if "Charge Capacity (mAh/g)" in validated_df.columns:
        validated_df["Charge Capacity (mAh/g)"] = pd.to_numeric(
            validated_df["Charge Capacity (mAh/g)"], errors="coerce"
        )
    if "Discharge Capacity (mAh/g)" in validated_df.columns:
        validated_df["Discharge Capacity (mAh/g)"] = pd.to_numeric(
            validated_df["Discharge Capacity (mAh/g)"], errors="coerce"
        )
    if "Specific Capacity (mAh/g)" in validated_df.columns:
        validated_df["Specific Capacity (mAh/g)"] = pd.to_numeric(
            validated_df["Specific Capacity (mAh/g)"], errors="coerce"
        )

    nan_columns = [
        col
        for col in raw_required
        if col in validated_df.columns and validated_df[col].isna().any()
    ]
    if nan_columns:
        raise ValueError(f"列包含非数值或缺失值: {nan_columns}")

    if "Time (s)" in validated_df.columns and (validated_df["Time (s)"] < 0).any():
        raise ValueError("Time (s) 列包含负值")
    if "Voltage (V)" in validated_df.columns and (
        (validated_df["Voltage (V)"] < 0).any()
        or (validated_df["Voltage (V)"] > 5).any()
    ):
        raise ValueError("Voltage (V) 列包含超出合理范围的值")
    if "Current (A)" in validated_df.columns and (validated_df["Current (A)"] == 0).all():
        raise ValueError("Current (A) 列全为零，无法计算容量，请检查数据")

    if "Charge Capacity (mAh/g)" in validated_df.columns and (
        validated_df["Charge Capacity (mAh/g)"].isna().any()
        or (validated_df["Charge Capacity (mAh/g)"] < 0).any()
    ):
        raise ValueError("Charge Capacity 列包含非数值或负值")
    if "Discharge Capacity (mAh/g)" in validated_df.columns and (
        validated_df["Discharge Capacity (mAh/g)"].isna().any()
        or (validated_df["Discharge Capacity (mAh/g)"] < 0).any()
      ):
        raise ValueError("Discharge Capacity 列包含非数值或负值")

    return validated_df.reset_index(drop=True)


def process_gcd_file(
    path: str,
    mass_mg: float = 2.5,
    sheet_name=None,
    delimiter=None,
    label: Optional[str] = None,
) -> pd.DataFrame:
    df = read_input_file(path, sheet_name=sheet_name, delimiter=delimiter)
    df = standardize_gcd_columns(df)
    df = validate_gcd_dataframe(df)
    df = calculate_specific_capacity(df, mass_mg=mass_mg)
    df = infer_gcd_segments(df)
    if label is not None:
        df = df.copy()
        df["Dataset"] = label
    return df


def build_gcd_summary(
    df: pd.DataFrame, current_density: str = "", voltage_window: str = ""
) -> dict:
    summary = {
        "Dataset": str(df["Dataset"].iloc[0]) if "Dataset" in df.columns else "",
        "current_density": current_density,
        "voltage_window": voltage_window,
    }
    summary.update(summarize_capacity(df))
    summary.update(compute_coulombic_efficiency(df))
    return summary


def calculate_specific_capacity(df: pd.DataFrame, mass_mg: float = 2.5) -> pd.DataFrame:
    result = df.copy()
    if "Specific Capacity (mAh/g)" in result.columns:
        result["Specific Capacity (mAh/g)"] = pd.to_numeric(
            result["Specific Capacity (mAh/g)"], errors="coerce"
        )
        return result

    if "Current (A)" not in result.columns or "Time (s)" not in result.columns:
        raise ValueError(
            "无法计算比容量：缺少 Current (A) 或 Time (s) 列，且未提供 Specific Capacity (mAh/g)。"
        )

    result["Delta Time (s)"] = result["Time (s)"].diff().fillna(result["Time (s)"])
    result["Capacity (mAh)"] = result["Current (A)"] * result["Delta Time (s)"] / 3600 * 1000
    result["Specific Capacity (mAh/g)"] = result["Capacity (mAh)"] / mass_mg
    return result


def infer_gcd_segments(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    if "Current (A)" in result.columns:
        current = result["Current (A)"].fillna(0)
        if (current > 0).any() and (current < 0).any():
            result["Segment"] = current.apply(lambda x: "Charge" if x > 0 else "Discharge" if x < 0 else "Unknown")
            return result

    if "Voltage (V)" in result.columns:
        dv = result["Voltage (V)"].diff().fillna(0)
        result["Segment"] = dv.apply(lambda x: "Charge" if x > 0 else "Discharge" if x < 0 else "Unknown")
        if result["Segment"].nunique() > 1:
            return result

    result["Segment"] = "Unknown"
    return result


def compute_coulombic_efficiency(df: pd.DataFrame) -> dict:
    if "Segment" not in df.columns or "Capacity (mAh)" not in df.columns:
        return {}

    summary = {}
    charge_capacity = df.loc[df["Segment"] == "Charge", "Capacity (mAh)"].abs().sum()
    discharge_capacity = df.loc[df["Segment"] == "Discharge", "Capacity (mAh)"].abs().sum()
    summary["charge_capacity_mAh"] = float(charge_capacity)
    summary["discharge_capacity_mAh"] = float(discharge_capacity)
    if charge_capacity > 0 and discharge_capacity > 0:
        summary["coulombic_efficiency_pct"] = float(discharge_capacity / charge_capacity * 100)
    return summary


def summarize_capacity(df: pd.DataFrame) -> dict:
    summary_df = df.copy()
    if "Specific Capacity (mAh/g)" not in summary_df.columns:
        summary_df = calculate_specific_capacity(summary_df)

    if "Specific Capacity (mAh/g)" not in summary_df.columns:
        raise ValueError(
            "无法汇总容量：数据中缺少 Specific Capacity (mAh/g) 列，且无法计算。"
        )

    spec_cap = pd.to_numeric(summary_df["Specific Capacity (mAh/g)"], errors="coerce")
    if spec_cap.isna().all():
        raise ValueError(
            "无法汇总容量：Specific Capacity (mAh/g) 列中没有可用数值。"
        )

    return {
        "mean_specific_capacity": float(spec_cap.mean()),
        "max_specific_capacity": float(spec_cap.max()),
        "min_specific_capacity": float(spec_cap.min()),
        "cycle_count": int(len(summary_df)),
    }


def plot_gcd_curves(df: pd.DataFrame, output_path: str | None = "gcd_curves_comparison.png") -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    if "Specific Capacity (mAh/g)" not in df.columns:
        df = calculate_specific_capacity(df)

    if "Curve" in df.columns:
        group_key = "Curve"
    elif "Dataset" in df.columns:
        group_key = "Dataset"
    else:
        group_key = None

    plot_groups = []
    if group_key and "Segment" in df.columns:
        grouped = df.groupby([group_key, "Segment"])
        for (dataset, segment), group in grouped:
            label = f"{dataset} ({segment})"
            plot_groups.append((label, group))
    elif group_key:
        grouped = df.groupby(group_key)
        for dataset, group in grouped:
            plot_groups.append((dataset, group))
    elif "Segment" in df.columns:
        grouped = df.groupby("Segment")
        for segment, group in grouped:
            plot_groups.append((segment, group))
    else:
        plot_groups = [("GCD Curve", df)]

    styles = ["-", "--", "-.", ":"]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    for idx, (label, group) in enumerate(plot_groups):
        style = styles[idx % len(styles)]
        color = colors[idx % len(colors)]
        ax.plot(
            group["Specific Capacity (mAh/g)"],
            group["Voltage (V)"],
            linestyle=style,
            marker="o",
            color=color,
            linewidth=1.2,
            label=str(label),
            alpha=0.8,
        )

    ax.set_xlabel("Specific Capacity (mAh/g)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title("GCD 比容量-电压曲线")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.8)
    ax.legend(fontsize=10)
    fig.tight_layout()

    if output_path:
        fig.savefig(output_path)
        plt.close(fig)
        print(f"已保存绘图文件: {output_path}")

    return fig


def export_results(df: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = output_dir / "GCD_results.xlsx"
    csv_path = output_dir / "GCD_results.csv"
    summary_path = output_dir / "summary_results.csv"

    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    df.to_csv(csv_path, index=False)
    summary = summarize_capacity(df)
    pd.DataFrame([summary]).to_csv(summary_path, index=False)

    print(f"已导出: {xlsx_path.name}, {csv_path.name}, {summary_path.name}")


def export_for_origin(df: pd.DataFrame, out_dir: Path) -> None:
    origin_path = out_dir / "Origin_export"
    origin_path.mkdir(parents=True, exist_ok=True)
    df.to_csv(origin_path / "gcd_all_data.csv", index=False)
    (origin_path / "README_for_Origin.txt").write_text(
        "使用Origin导入步骤:\n"
        "1. 打开OriginPro。\n"
        "2. 文件 > 导入 > 单个ASCII，选择 gcd_all_data.csv。\n"
        "3. 使用数据绘制 Specific Capacity vs Voltage。\n"
        "4. 保存为 .opju 项目文件。\n"
    )
    print(f"已生成Origin导入数据于: {origin_path}")


def save_error_log(stage: str, exc: Exception) -> None:
    message = f"[{stage}] {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    print(message)


def generate_sample_gcd_dataframe() -> pd.DataFrame:
    data = {
        "Cycle": list(range(1, 21)),
        "Charge Capacity (mAh/g)": [50 + i * 1.2 for i in range(20)],
        "Discharge Capacity (mAh/g)": [48 + i * 1.1 for i in range(20)],
        "Voltage (V)": [1.2 - 0.005 * i for i in range(20)],
        "Current (A)": [0.1 for _ in range(20)],
        "Time (s)": [i * 30 for i in range(20)],
    }
    return pd.DataFrame(data)

__all__ = [
    "_normalize_column_name",
    "read_input_file",
    "choose_input_files",
    "standardize_gcd_columns",
    "validate_gcd_dataframe",
    "calculate_specific_capacity",
    "infer_gcd_segments",
    "compute_coulombic_efficiency",
    "summarize_capacity",
    "plot_gcd_curves",
    "export_results",
    "export_for_origin",
    "save_error_log",
    "generate_sample_gcd_dataframe",
]
