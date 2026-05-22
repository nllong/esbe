"""Shared helpers for the ESBE analysis notebooks.

This module collects the small bits of boilerplate that previously repeated
across every ``.ipynb`` in this repo. There are two broad groups of helpers:

* **Notebook plumbing** — selecting between the local and Docker URBANopt CLI
  wrappers, building the standard set of working-directory paths, applying the
  usual warning filters.
* **Plotting helpers** — bar plots of end-use summaries, seasonal box plots,
  grid-metric box plots, and load-duration curves. These all operate on a
  :class:`urbanopt_des.urbanopt_analysis.URBANoptAnalysis` instance and write
  PNGs / CSVs into a caller-provided summary directory.

Domain logic that belongs to URBANopt itself (mapper edits, project setup,
path resolution, post-process bootstrap) lives in the ``urbanopt-des``
package rather than here. See:

* :meth:`urbanopt_des.uo_cli_wrapper.UOCliWrapper.bootstrap_project`
* :meth:`urbanopt_des.uo_cli_wrapper.UOCliWrapper.enable_measures_in_mapper`
* :meth:`urbanopt_des.uo_cli_wrapper.UOCliWrapper.copy_template_mappers`
* :meth:`urbanopt_des.urbanopt_analysis.URBANoptAnalysis.resolve_uo_project_paths`
* :meth:`urbanopt_des.urbanopt_analysis.URBANoptAnalysis.bootstrap_from_uo_results`
"""

from __future__ import annotations

import os
import shutil
import warnings
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Iterable, Optional, Sequence

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default URBANopt CLI Docker image tag used across the ESBE notebooks.
DEFAULT_DOCKER_IMAGE_TAG = "urbanopt-cli:1.2-ubuntu22"

#: Default Matplotlib figure size for per-analysis plots (8x4 inches).
GRAPH_SIZE = (8, 4)

#: Default Matplotlib figure size for combined / multi-series plots.
GRAPH_SIZE_WIDE = (9, 5)

#: End-use rows (in the order to plot) mapped to bar colors. The keys must
#: match the row labels in ``uo_analysis.end_use_summary``.
ENERGY_END_USE_ROWS = {
    "Interior Lighting": "#FFFFCC",
    "Exterior Lighting": "lightblue",
    "Plug Loads": "brown",
    "Building Cooling": "blue",
    "District Cooling": "blue",
    "District Heating": "orange",
    "Building Heating": "orange",
    "Building Fans": "lightgray",
    "Building Pumps": "lightblue",
    "Building Heat Rejection": "royalblue",
    "Building Water Systems": "#FFBB78",
    "ETS Pump Total": "lightgreen",
    "ETS Heat Pump": "gold",
    "Sewer Pump": "darkgray",
    "GHX Pump": "darkgreen",
    "Distribution Pump": "darkblue",
}

#: Days of the week ordered Sunday-first to use as a `seaborn.boxplot` `order=`.
WEEKDAY_ORDER_SUNDAY_FIRST = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]

#: Default energy variables to plot in seasonal box plots.
DEFAULT_ENERGY_VARS = (
    "Total Electricity",
    "Total Natural Gas",
    "Total Energy",
)

#: Default daily-grid-metric variables to plot in monthly/weekday box plots.
DEFAULT_GRID_METRIC_VARS = (
    "Total Electricity Max",
    "Total Electricity Load Factor",
    "Total Electricity System Ramping",
    "Total Electricity PVR",
    "Total Natural Gas Max",
    "Total Natural Gas Load Factor",
    "Total Natural Gas System Ramping",
)

#: Default variables for combined grid-metric box plots (electricity-focused).
DEFAULT_COMBINED_GRID_METRIC_VARS = (
    "Total Electricity Max",
    "Total Electricity Load Factor",
    "Total Electricity System Ramping",
    "Total Electricity PVR",
)

#: Default load-duration-curve variables.
DEFAULT_LDC_VARS = ("Total Electricity", "Total Natural Gas", "Total Energy")


# ---------------------------------------------------------------------------
# Notebook plumbing
# ---------------------------------------------------------------------------


@dataclass
class NotebookPaths:
    """The set of directory paths every analysis notebook starts from.

    Attributes:
        workdir: Notebook working directory (``Path().resolve()``).
        analysis_dir: Per-project analysis root (``workdir / "esbe_2026"``).
        template_data_dir: Template data root (``workdir / "data" / "templates"``).
        num_usable_cores: Suggested parallelism for URBANopt CLI runs.
    """

    workdir: Path
    analysis_dir: Path
    template_data_dir: Path
    num_usable_cores: int

    def activity_dir(self, name: str) -> Path:
        """Return ``analysis_dir / name``, creating it if it does not exist."""
        path = self.analysis_dir / name
        path.mkdir(parents=True, exist_ok=True)
        return path


def setup_notebook_paths(
    workdir: Optional[Path] = None,
    analysis_subdir: str = "esbe_2026",
    template_subdir: str = "data/templates",
    cores_offset: int = 1,
    quiet: bool = False,
) -> NotebookPaths:
    """Build the standard set of notebook paths and report them.

    Args:
        workdir: Override for the working directory. Defaults to ``Path().resolve()``
            (the directory the notebook is running from).
        analysis_subdir: Subdirectory of ``workdir`` to use as the analysis root.
            Created if it does not already exist.
        template_subdir: Subdirectory of ``workdir`` that holds template data.
        cores_offset: Number to subtract from ``os.cpu_count()`` to leave
            headroom for the rest of the system. Pass ``2`` on machines where
            URBANopt and Docker compete for cores.
        quiet: If True, suppress the informational ``print`` statements.

    Returns:
        NotebookPaths: A bundle containing ``workdir``, ``analysis_dir``,
        ``template_data_dir``, and ``num_usable_cores``.
    """
    workdir = Path(workdir).resolve() if workdir is not None else Path().resolve()
    analysis_dir = workdir / analysis_subdir
    analysis_dir.mkdir(parents=True, exist_ok=True)
    template_data_dir = workdir / template_subdir
    num_usable_cores = max(1, (os.cpu_count() or 1) - cores_offset)

    if not quiet:
        print(f"Working directory: {workdir}")
        print(f"template_data_dir: {template_data_dir}")
        print(f"analysis_dir: {analysis_dir}")
        print(f"Number of usable cores for parallel processing: {num_usable_cores}")

    return NotebookPaths(
        workdir=workdir,
        analysis_dir=analysis_dir,
        template_data_dir=template_data_dir,
        num_usable_cores=num_usable_cores,
    )


def select_uo_class(
    use_docker: bool = False, docker_image_tag: str = DEFAULT_DOCKER_IMAGE_TAG
):
    """Return the URBANopt CLI wrapper class (or partial) to use.

    Args:
        use_docker: If True, route ``uo`` commands through the
            :class:`tools.docker_uo_cli_wrapper.DockerUOCliWrapper` container.
            If False (default), use the locally installed URBANopt CLI via
            :class:`urbanopt_des.uo_cli_wrapper.UOCliWrapper`.
        docker_image_tag: Docker image tag to bind into the partial when
            ``use_docker`` is True.

    Returns:
        Either ``UOCliWrapper`` directly or ``partial(DockerUOCliWrapper, image_tag=...)``,
        callable with the same positional arguments either way.
    """
    if use_docker:
        # Imported lazily so docker tools are optional for non-docker users.
        from tools.docker_uo_cli_wrapper import DockerUOCliWrapper

        return partial(DockerUOCliWrapper, image_tag=docker_image_tag)

    from urbanopt_des.uo_cli_wrapper import UOCliWrapper

    return UOCliWrapper


def copy_activity_to_new_location(source_dir, dest_dir, overwrite=False):
    """Copy a directory from one location to another as a starting point.

    Args:
        source_dir: Path object pointing to the source directory
        dest_dir: Path object pointing to the destination directory
        overwrite: Whether to overwrite an existing destination directory. Default is False.
    """
    source_dir = Path(source_dir)
    dest_dir = Path(dest_dir)

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    if dest_dir.exists():
        if overwrite:
            print(f"Warning: {dest_dir} already exists. Overwriting...")
            shutil.rmtree(dest_dir)
            shutil.copytree(source_dir, dest_dir)
            print(f"Copied {source_dir} to {dest_dir}")
        else:
            print(f"⚠️  Warning: Destination directory already exists at: {dest_dir}")
            print("   Skipping copy. Using existing directory.")
            print("   To overwrite, call with overwrite=True")
        return dest_dir

    shutil.copytree(source_dir, dest_dir)
    print(f"Copied {source_dir} to {dest_dir}")
    return dest_dir


def silence_common_warnings() -> None:
    """Apply the warning filters every post-process notebook used to set inline.

    Silences ``RuntimeWarning``, ``DeprecationWarning``, ``UserWarning`` and
    ``FutureWarning`` so analysis cells are not buried in noise. Notebooks that
    want to see one specific category can call ``warnings.resetwarnings()``
    afterward and reapply only what they want.
    """
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=UserWarning)
    warnings.simplefilter(action="ignore", category=FutureWarning)


def apply_default_style(graph_size: tuple = GRAPH_SIZE) -> tuple:
    """Apply the default seaborn style used by the notebooks and return ``graph_size``.

    Calling ``sns.set_style("whitegrid")`` inline at the top of a notebook is
    safe to repeat, but tucking it into a helper keeps the imports tidy.
    """
    sns.set_style("whitegrid")
    return graph_size


# ---------------------------------------------------------------------------
# Internal plotting helpers
# ---------------------------------------------------------------------------


def _analysis_iter(uo_analysis) -> list[str]:
    """Return the canonical iteration order: Non-Connected first, then Modelica keys."""
    return ["Non-Connected", *list(uo_analysis.modelica.keys())]


def _series_for_analysis(uo_analysis, analysis_name: str, attr_name: str):
    """Pull a dataframe off ``uo_analysis.urbanopt`` or ``uo_analysis.modelica[name]``.

    Args:
        uo_analysis: The :class:`URBANoptAnalysis` instance.
        analysis_name: Either ``"Non-Connected"`` or a Modelica key.
        attr_name: Attribute to read off the result object (e.g. ``"data"``,
            ``"min_60_with_buildings"``, ``"grid_metrics_daily"``,
            ``"data_15min"``).

    Returns:
        The dataframe at ``getattr(result, attr_name)``.
    """
    if analysis_name == "Non-Connected":
        return getattr(uo_analysis.urbanopt, attr_name)
    return getattr(uo_analysis.modelica[analysis_name], attr_name)


def _display_name(uo_analysis, analysis_name: str) -> str:
    """Resolve the display name for ``analysis_name`` (Non-Connected stays as-is)."""
    if analysis_name == "Non-Connected":
        return "Non-Connected"
    return uo_analysis.modelica[analysis_name].display_name


def _format_thousands_y_axis(ax) -> None:
    """Add a ``"{:,}"`` thousands-separator formatter to ``ax``'s y axis."""
    ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, _loc: f"{int(x):,}"))


def _padded_limits(y_min: float, y_max: float, pad: float = 0.2) -> tuple:
    """Return ``(y_min, y_max)`` padded by ``pad`` (and snapped to 0 when close).

    Mirrors the per-cell pad/clip logic in the original notebooks so the
    plots produced by helpers match what the notebooks used to draw.
    """
    if y_min + y_max < 0:
        y_min = y_min * (1 + pad)
        y_max = y_max * (1 - pad)
    else:
        y_min = y_min * (1 - pad)
        y_max = y_max * (1 + pad)

    if abs(y_min) < 1 and abs(y_max) < 1:
        return y_min, y_max

    if abs(y_min) < 1:
        y_min = 0
    if abs(y_max) < 1:
        y_max = 0
    return y_min, y_max


def _grid_metric_ylabel(var: str) -> tuple:
    """Return ``(ylabel, save_name, y_min, y_max)`` for a daily-grid-metric ``var``.

    Captures the if/elif ladder that classified each metric in the original
    notebooks. ``y_min`` / ``y_max`` are ``None`` unless the metric has a
    natural [0, 1] range (Load Factor).
    """
    if "System Ramping" in var:
        return f"{var} (MW)", "system_ramping", None, None
    if "Load Factor" in var:
        return f"{var} (Ratio)", "load_factor", 0.0, 1.0
    return f"{var} (W)", "electricity", None, None


# ---------------------------------------------------------------------------
# Plotting helpers (public)
# ---------------------------------------------------------------------------


def plot_end_use_bar_non_connected(
    uo_analysis,
    results_summary_dir: Path,
    end_use_rows: dict = ENERGY_END_USE_ROWS,
    graph_size: tuple = GRAPH_SIZE,
    csv_name: str = "end_use_summary_non_connected.csv",
    png_name: str = "bar_end_use_summary_all.png",
):
    """Bar plot of the *Non-Connected* end-use summary in MWh.

    Drops all columns except ``"Non-Connected"``, drops rows whose value is 0,
    subsets ``end_use_rows`` to only what's present, divides by 1e6 to convert
    Wh -> MWh, then renders a stacked horizontal-axis bar plot.

    Saves the underlying dataframe to ``csv_name`` and the plot to ``png_name``
    inside ``results_summary_dir``.

    Args:
        uo_analysis: A :class:`URBANoptAnalysis` with ``end_use_summary`` populated.
        results_summary_dir: Directory to write the CSV and PNG into.
        end_use_rows: Mapping of end-use row name to bar color.
        graph_size: Matplotlib figure size.
        csv_name: Output CSV filename.
        png_name: Output PNG filename.
    """
    df_to_plot = uo_analysis.end_use_summary.copy()
    columns_to_drop = [
        col for col in df_to_plot.columns if col not in ["Non-Connected"]
    ]
    df_to_plot = df_to_plot.drop(columns=columns_to_drop)

    df_to_plot = df_to_plot[df_to_plot["Non-Connected"] > 0]
    rows_with_data = df_to_plot.index.tolist()
    end_use_rows_sub = {k: v for k, v in end_use_rows.items() if k in rows_with_data}

    df_to_plot = df_to_plot.T / 1e6
    df_to_plot = df_to_plot[end_use_rows_sub.keys()]

    csv_path = results_summary_dir / csv_name
    df_to_plot.to_csv(csv_path)
    print(f"Saved {csv_path}")

    df_to_plot.plot.bar(
        figsize=graph_size, stacked=True, color=end_use_rows_sub.values()
    )
    plt.legend(
        fontsize="x-small",
        bbox_to_anchor=(1.05, 1),
        loc="upper left",
        borderaxespad=0.0,
    )
    plt.tight_layout()
    plt.subplots_adjust(left=0.1)
    plt.ylabel("Total Energy [MWh]")
    plt.xticks(rotation=0)
    _format_thousands_y_axis(plt.gca())

    png_path = results_summary_dir / png_name
    plt.savefig(png_path, dpi=300)
    plt.show()


def plot_end_use_bar_all(
    uo_analysis,
    project_summary_dir: Path,
    end_use_rows: dict = ENERGY_END_USE_ROWS,
    analysis_to_exclude: Optional[Iterable[str]] = None,
    csv_name: str = "end_use_summary_all.csv",
    png_name: str = "bar_end_use_summary_all.png",
):
    """Bar plot of the *full* end-use summary across all analyses.

    Drops a ``Units`` column (if present) and any analyses named in
    ``analysis_to_exclude`` (those names are looked up through
    :meth:`URBANoptAnalysis.display_name_mappings`). Values are converted from
    Wh to MWh and reordered by ``end_use_rows``.

    Args:
        uo_analysis: Analysis with ``end_use_summary`` populated and Modelica
            results already attached.
        project_summary_dir: Cross-scenario summary directory to write into.
        end_use_rows: Mapping of end-use row name to bar color.
        analysis_to_exclude: Optional sequence of analysis keys to drop before
            plotting.
        csv_name: Output CSV filename.
        png_name: Output PNG filename.
    """
    analysis_to_exclude = list(analysis_to_exclude or [])
    display_map = uo_analysis.display_name_mappings()
    exclude_display = [display_map[a] for a in analysis_to_exclude]

    df_to_plot = uo_analysis.end_use_summary.copy()
    if exclude_display:
        df_to_plot = df_to_plot.drop(columns=exclude_display)
    if "Units" in df_to_plot.columns:
        df_to_plot = df_to_plot.drop(columns="Units")
    df_to_plot = df_to_plot.T / 1e6
    df_to_plot = df_to_plot[list(end_use_rows.keys())]

    csv_path = project_summary_dir / csv_name
    df_to_plot.to_csv(csv_path)
    print(f"Saved {csv_path}")

    df_to_plot.plot.bar(figsize=(9, 6), stacked=True, color=end_use_rows.values())
    plt.legend(
        fontsize=10, bbox_to_anchor=(1.05, 1), loc="upper left", borderaxespad=0.0
    )
    plt.tight_layout()
    plt.subplots_adjust(left=0.1)
    plt.ylabel("Total Energy [MWh]")
    plt.xticks(rotation=0)
    _format_thousands_y_axis(plt.gca())

    png_path = project_summary_dir / png_name
    plt.savefig(png_path, dpi=300)
    plt.show()


def plot_seasonal_boxplots(
    uo_analysis,
    output_dir: Path,
    vars_to_plot: Sequence[str] = DEFAULT_ENERGY_VARS,
    graph_size: tuple = GRAPH_SIZE,
    warmup_offset: int = 48,
):
    """Per-analysis monthly and weekday box plots for the given energy variables.

    For each analysis (Non-Connected + every Modelica result attached to
    ``uo_analysis``) and each variable in ``vars_to_plot``:

    * Skip vars whose sum is zero.
    * Drop the first ``warmup_offset`` timesteps (default 48 = the leading
      warm-up "peak" that distorts the y-axis).
    * Convert Wh -> MWh, pad the y-limits by 20%.
    * Render monthly and weekday box plots side-by-side and save them as PNGs.

    Args:
        uo_analysis: The analysis instance.
        output_dir: Directory to write PNGs into.
        vars_to_plot: Iterable of column names to plot.
        graph_size: Matplotlib figure size.
        warmup_offset: Number of leading rows to drop before plotting.
    """
    for analysis_name in _analysis_iter(uo_analysis):
        attr = "data" if analysis_name == "Non-Connected" else "min_60_with_buildings"
        df_season = _series_for_analysis(uo_analysis, analysis_name, attr)

        for var_to_plot in vars_to_plot:
            str_analysis_name = analysis_name.lower().replace(" ", "_")
            str_vars_to_plot = var_to_plot.lower().replace(" ", "_")

            if df_season[var_to_plot].sum() == 0:
                print(
                    f"Skipping plot for {analysis_name} - {var_to_plot} (sum is zero)"
                )
                continue

            df_season = df_season.iloc[warmup_offset:]

            var_y_min = df_season[var_to_plot].min() / 1e6
            var_y_max = df_season[var_to_plot].max() / 1e6
            var_y_min, var_y_max = _padded_limits(var_y_min, var_y_max)

            _fig, ax = plt.subplots(figsize=graph_size)
            sns.boxplot(
                data=df_season / 1e6, x=df_season.index.month, y=var_to_plot, ax=ax
            )
            ax.set_ylabel(f"{var_to_plot} (MW)")
            ax.set_xlabel("Month")
            ax.set_ylim(var_y_min, var_y_max)
            plt.title(analysis_name)
            plt.tight_layout()
            plt.savefig(
                output_dir
                / f"monthly_boxplot_{str_vars_to_plot}_{str_analysis_name}.png",
                dpi=300,
            )

            _fig, ax = plt.subplots(figsize=graph_size)
            sns.boxplot(
                data=df_season / 1e6, x=df_season.index.day_name(), y=var_to_plot, ax=ax
            )
            ax.set_ylabel(f"{var_to_plot} (MW)")
            ax.set_ylim(var_y_min, var_y_max)
            plt.title(analysis_name)
            plt.tight_layout()
            plt.savefig(
                output_dir
                / f"weekday_boxplot_{str_vars_to_plot}_{str_analysis_name}.png",
                dpi=300,
            )


def plot_combined_monthly_boxplots(
    uo_analysis,
    output_dir: Path,
    vars_to_plot: Sequence[str] = DEFAULT_ENERGY_VARS,
    warmup_offset: int = 48,
):
    """Monthly box plots that overlay every analysis as hue groups.

    For each variable in ``vars_to_plot``, concatenates one dataframe per
    analysis (Non-Connected + every Modelica result), labels each row with the
    analysis display name, drops the warm-up window, and renders a single
    seaborn box plot with ``hue="Analysis"`` and ``dodge=True``.

    Args:
        uo_analysis: The analysis instance.
        output_dir: Directory to write PNGs into.
        vars_to_plot: Iterable of column names to plot.
        warmup_offset: Number of leading rows to drop before plotting.
    """
    for var_to_plot in vars_to_plot:
        combined_df = []

        for analysis_name in _analysis_iter(uo_analysis):
            if analysis_name == "Non-Connected":
                df_season = uo_analysis.urbanopt.data.copy() / 1e6
                df_season["Analysis"] = analysis_name
            else:
                df_season = (
                    uo_analysis.modelica[analysis_name].min_60_with_buildings.copy()
                    / 1e6
                )
                df_season["Analysis"] = uo_analysis.modelica[analysis_name].display_name

            df_season = df_season.iloc[warmup_offset:]
            combined_df.append(df_season)

        combined_df = pd.concat(combined_df)

        _fig, ax = plt.subplots(figsize=GRAPH_SIZE_WIDE)
        sns.boxplot(
            data=combined_df,
            x=combined_df.index.month,
            y=var_to_plot,
            hue="Analysis",
            dodge=True,
            width=0.7,
            ax=ax,
        )

        y_max = combined_df[var_to_plot].max() * 1.2
        ax.set_ylabel(f"{var_to_plot} (MW)")
        ax.set_xlabel("Month")
        ax.set_ylim(0, y_max)
        plt.tight_layout()
        plt.savefig(
            output_dir / f"monthly_boxplot_{var_to_plot.lower().replace(' ', '_')}.png",
            dpi=300,
        )
        plt.show()


def plot_grid_metric_boxplots(
    uo_analysis,
    output_dir: Path,
    vars_to_plot: Sequence[str] = DEFAULT_GRID_METRIC_VARS,
):
    """Per-analysis monthly + weekday box plots for daily grid metrics.

    For each analysis and each metric, choose a label and y-range based on the
    metric type (Load Factor -> [0, 1], System Ramping -> MW, otherwise W),
    draw monthly and weekday box plots, and save them.

    Args:
        uo_analysis: The analysis instance.
        output_dir: Directory to write PNGs into.
        vars_to_plot: Daily grid metrics to plot.
    """
    for analysis_name in _analysis_iter(uo_analysis):
        df_box = _series_for_analysis(uo_analysis, analysis_name, "grid_metrics_daily")

        for var_to_plot in vars_to_plot:
            y_min_data = df_box[var_to_plot].min() * 0.8
            y_max_data = df_box[var_to_plot].max() * 1.2
            ylabel, _save, y_min_fixed, y_max_fixed = _grid_metric_ylabel(var_to_plot)
            y_min = y_min_fixed if y_min_fixed is not None else y_min_data
            y_max = y_max_fixed if y_max_fixed is not None else y_max_data

            var_to_plot_str = var_to_plot.lower().replace(" ", "_")

            _fig, ax = plt.subplots(figsize=(8, 5))
            sns.boxplot(data=df_box, x=df_box.index.month, y=var_to_plot, ax=ax)
            ax.set_ylabel(ylabel)
            ax.set_xlabel("Month")
            if y_max:
                ax.set_ylim(y_min if y_min else 0, y_max)
            plt.title(analysis_name)
            plt.tight_layout()
            plt.savefig(
                output_dir
                / f"monthly_grid_metric_{var_to_plot_str}_{analysis_name}.png",
                dpi=300,
            )
            plt.show()

            _fig, ax = plt.subplots(figsize=(8, 5))
            sns.boxplot(
                data=df_box,
                x=df_box.index.day_name(),
                y=var_to_plot,
                ax=ax,
                order=WEEKDAY_ORDER_SUNDAY_FIRST,
            )
            ax.set_ylabel(ylabel)
            ax.set_xlabel("Day of Week")
            if y_max:
                ax.set_ylim(y_min if y_min else 0, y_max)
            plt.title(analysis_name)
            plt.tight_layout()
            plt.savefig(
                output_dir
                / f"weekday_grid_metric_{var_to_plot_str}_{analysis_name}.png",
                dpi=300,
            )
            plt.show()


def plot_combined_grid_metric_boxplots(
    uo_analysis,
    output_dir: Path,
    vars_to_plot: Sequence[str] = DEFAULT_COMBINED_GRID_METRIC_VARS,
):
    """Monthly + weekday box plots that overlay every analysis as hue groups.

    Like :func:`plot_combined_monthly_boxplots` but for daily grid metrics
    rather than 60-minute energy series. Load-Factor metrics are clipped to
    [0.4, 0.9] (the empirically useful window for these projects).
    """
    for var_to_plot in vars_to_plot:
        combined_df = []

        for analysis_name in _analysis_iter(uo_analysis):
            df_box = _series_for_analysis(
                uo_analysis, analysis_name, "grid_metrics_daily"
            )
            df_box["Analysis"] = _display_name(uo_analysis, analysis_name)
            combined_df.append(df_box)

        combined_df = pd.concat(combined_df)
        var_to_plot_str = var_to_plot.lower().replace(" ", "_")

        # Pick y-axis bounds + label based on the metric type
        if "System Ramping" in var_to_plot:
            ylabel = f"{var_to_plot} (MW)"
            y_min, y_max = 0, combined_df[var_to_plot].max() * 1.2
        elif "Load Factor" in var_to_plot:
            ylabel = f"{var_to_plot} (Ratio)"
            y_min, y_max = 0.4, 0.9
        elif "PVR" in var_to_plot:
            ylabel = f"{var_to_plot}"
            y_min, y_max = 0, combined_df[var_to_plot].max() * 1.2
        else:
            ylabel = f"{var_to_plot} (W)"
            y_min, y_max = 0, combined_df[var_to_plot].max() * 1.2

        _fig, ax = plt.subplots(figsize=GRAPH_SIZE_WIDE)
        sns.boxplot(
            data=combined_df,
            x=combined_df.index.month,
            y=var_to_plot,
            hue="Analysis",
            dodge=True,
            width=0.7,
            ax=ax,
        )
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Month")
        ax.set_ylim(y_min, y_max)
        plt.tight_layout()
        plt.savefig(
            output_dir / f"monthly_grid_metric_{var_to_plot_str}_combined.png",
            dpi=300,
        )
        plt.show()

        _fig, ax = plt.subplots(figsize=(8, 5))
        sns.boxplot(
            data=combined_df,
            x=combined_df.index.day_name(),
            y=var_to_plot,
            hue="Analysis",
            ax=ax,
            order=WEEKDAY_ORDER_SUNDAY_FIRST,
        )
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Day of Week")
        ax.set_ylim(y_min, y_max)
        plt.tight_layout()
        plt.savefig(
            output_dir / f"weekday_grid_metric_{var_to_plot_str}_combined.png",
            dpi=300,
        )
        plt.show()


def plot_load_duration_curves(
    uo_analysis,
    output_dir: Path,
    ldc_vars: Sequence[str] = DEFAULT_LDC_VARS,
    zoom_hours: int = 100,
):
    """Plot Load Duration Curves (full + zoomed) for the given variables.

    For each variable in ``ldc_vars`` and each analysis attached to
    ``uo_analysis``, resample the 15-minute series to hourly maxima, sort
    descending, build a ``(Hour Rank, Load, Analysis)`` long-form dataframe and
    plot it. Two PNGs are written per variable: the full LDC and the first
    ``zoom_hours`` hours.

    Args:
        uo_analysis: The analysis instance.
        output_dir: Directory to write PNGs into.
        ldc_vars: Variables to plot.
        zoom_hours: How many leading hours to include in the zoomed plot.
    """
    for ldc_var in ldc_vars:
        combined_ldc_df = []
        combined_ldc_df_zoom = []

        for analysis_name in _analysis_iter(uo_analysis):
            if analysis_name == "Non-Connected":
                df_15min = uo_analysis.urbanopt.data_15min[ldc_var].copy()
            else:
                df_15min = (
                    uo_analysis.modelica[analysis_name]
                    .min_15_with_buildings[ldc_var]
                    .copy()
                )
            df_hourly = df_15min.resample("H").max()
            display_name = _display_name(uo_analysis, analysis_name)

            ldc_series = df_hourly.sort_values(ascending=False).reset_index(drop=True)
            ldc_df = pd.DataFrame(
                {
                    "Hour Rank": range(1, len(ldc_series) + 1),
                    "Load (W)": ldc_series,
                    "Analysis": display_name,
                }
            )
            combined_ldc_df.append(ldc_df)
            combined_ldc_df_zoom.append(ldc_df.head(zoom_hours))

        combined_ldc_df = pd.concat(combined_ldc_df)
        combined_ldc_df_zoom = pd.concat(combined_ldc_df_zoom)

        fig, ax = plt.subplots(figsize=GRAPH_SIZE_WIDE)
        sns.lineplot(
            data=combined_ldc_df, x="Hour Rank", y="Load (W)", hue="Analysis", ax=ax
        )
        ax.set_ylabel(f"{ldc_var} Load (W)")
        ax.set_xlabel("Hour of Year (Sorted by Load)")
        ax.set_xlim(0, combined_ldc_df["Hour Rank"].max() + 20)
        ax.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        filename = f"load_duration_curve_{ldc_var.lower().replace(' ', '_')}.png"
        plt.savefig(output_dir / filename, dpi=300)
        print(f"Saved {filename}")
        plt.show()

        fig, ax = plt.subplots(figsize=GRAPH_SIZE_WIDE)
        sns.lineplot(
            data=combined_ldc_df_zoom,
            x="Hour Rank",
            y="Load (W)",
            hue="Analysis",
            ax=ax,
        )
        ax.set_ylabel(f"{ldc_var} Load (W)")
        ax.set_xlabel("Hour of Year (Sorted by Load)")
        ax.set_xlim(0, zoom_hours)
        ax.grid(True, linestyle="--", alpha=0.6)
        plt.tight_layout()
        filename_zoom = f"load_duration_curve_{ldc_var.lower().replace(' ', '_')}_first{zoom_hours}.png"
        plt.savefig(output_dir / filename_zoom, dpi=300)
        print(f"Saved {filename_zoom}")
        plt.show()
