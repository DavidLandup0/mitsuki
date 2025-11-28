import os
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

BACKGROUND_COLOR = "#fff4ec"
SPINE_COLOR = "#444"


def parse_wrk_output(file_path):
    """Parses wrk output and returns requests per second (avg and stdev)."""
    if not os.path.exists(file_path):
        return 0.0, 0.0
    with open(file_path, "r") as f:
        content = f.read()
        req_sec_match = re.search(r"Requests/sec:\s*(\d+\.\d+)", content)

        thread_stats_match = re.search(
            r"Req/Sec\s+\d+\.\d+k?\s+(\d+\.\d+k?)\s+", content
        )

        if thread_stats_match:
            stdev_str = thread_stats_match.group(1)

            def parse_k_value(s):
                s = s.lower()
                if s.endswith("k"):
                    return float(s[:-1]) * 1000
                return float(s)

            stdev = parse_k_value(stdev_str)
            total_req_sec = float(req_sec_match.group(1)) if req_sec_match else 0.0
            return total_req_sec, stdev

        elif req_sec_match:
            return float(req_sec_match.group(1)), 0.0

    return 0.0, 0.0


def generate_plot(results_df, title, output_path):
    results_df["RPS"] = pd.to_numeric(results_df["RPS"], errors="coerce")
    results_df["Stdev"] = pd.to_numeric(results_df["Stdev"], errors="coerce").fillna(0)
    results_df.dropna(subset=["RPS"], inplace=True)

    fig, ax = plt.subplots(figsize=(6, 3))
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(SPINE_COLOR)
    ax.spines["bottom"].set_color(SPINE_COLOR)
    ax.tick_params(colors=SPINE_COLOR)

    full_palette = [
        "#ffcdde",
        "#7efaff",
        "#1adee6",
        "#dfbee8",
        "#7ec3ed",
        "#616ca8",
        "#8180b4",
        "#f6f9f6",
    ]

    colors = []
    idx = 0
    for fw in results_df["Framework"]:
        if "mitsuki" in fw.lower():
            # Maintain color for mitsuki :D
            colors.append("#fea2ba")
        else:
            colors.append(full_palette[idx % len(full_palette)])
            idx += 1

    x = np.arange(len(results_df))

    sns.barplot(
        x="Framework",
        y="RPS",
        hue="Framework",
        data=results_df,
        palette=colors,
        ax=ax,
        edgecolor="none",
        legend=False,
    )

    ax.errorbar(
        x,
        results_df["RPS"],
        yerr=results_df["Stdev"],
        fmt="none",
        ecolor="#444",
        capsize=3,
        linewidth=1,
        zorder=10,
    )

    ax.set_xticks(x)
    ax.set_xticklabels(results_df["Framework"], rotation=30, ha="right", fontsize=10)
    ax.set_ylabel("Requests/sec", fontsize=12)
    ax.set_title(title, fontsize=16, pad=15)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"Generated plot: {output_path}")


def process_results(results_dir, local=False):
    """Processes all result files in a directory."""
    frameworks = [
        # We run benchmarks on granian, uvicorn and socketify
        # but report the default server - granian.
        "mitsuki-granian",
        "fastapi",
        "flask",
        "django",
        "elysia",
        "express",
        "spring",
        "gin",
    ]
    results = []
    suffix = "-local" if local else ""
    for framework in frameworks:
        file_path = os.path.join(results_dir, f"{framework}{suffix}.txt")
        rps, stdev = parse_wrk_output(file_path)
        if rps > 0:
            # Trim server names from mitsuki for cleaner display
            if framework == "mitsuki-granian":
                framework = "mitsuki"
            results.append({"Framework": framework, "RPS": rps, "Stdev": stdev})

    if not results:
        return None

    df = pd.DataFrame(results)
    df = df.sort_values(by="RPS", ascending=False).reset_index(drop=True)
    return df


def generate_markdown_table(df):
    """Generates a markdown table from a dataframe."""
    if df is None or df.empty:
        return ""
    header = "| " + " | ".join(df.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    body = "\n".join(
        ["| " + " | ".join(map(str, row)) + " |" for row in df.itertuples(index=False)]
    )
    print(header + "\n" + separator + "\n" + body)


def main():
    docker_results_df = process_results("results")
    local_results_df = process_results("results", local=True)

    generate_plot(
        docker_results_df,
        "Out-Of-The-Box Requests Per Second - Docker",
        "results/benchmark_results.png",
    )
    generate_markdown_table(docker_results_df)

    generate_plot(
        local_results_df,
        "Out-Of-The-Box Requests Per Second - Local",
        "results/local_benchmark_results.png",
    )
    generate_markdown_table(local_results_df)


if __name__ == "__main__":
    main()
