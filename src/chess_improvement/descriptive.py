"""Phase 2: descriptive analysis of blitz results, with no engine involved.

Every rate is reported with n and a 95% CI. Comparisons that adjust for opponent
strength use the *residual*: actual score minus the Elo-expected score at the time
of the game (see stats.residual_summary).

Outputs: reports/phase2/*.png and reports/phase2/summary.md

Run:  uv run python -m chess_improvement.descriptive
"""
from __future__ import annotations

import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import GAMES_TABLE, REPORTS_DIR
from .stats import residual_summary, wilson_ci

OUT = REPORTS_DIR / "phase2"
CONTROLS = {"180": "3+0", "300": "5+0"}  # time_control -> label; the two controls in scope
# Colours from the validated categorical palette (slot 1 blue, slot 2 orange). They follow the
# time control, never its rank.
COLOURS = {"3+0": "#2a78d6", "5+0": "#eb6834"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

# chess.com stores UTC. Matt confirmed he plays on UK time.
LOCAL_TZ = "Europe/London"
SESSION_GAP = pd.Timedelta(minutes=30)  # a gap longer than this between games starts a new session
TIME_TROUBLE_FRAC = 0.10                # "time trouble" = my clock below 10% of the base time

# Coarse move-number phases, used only until the engine phase supplies material-based phases.
PHASE_BINS = [0, 10, 30, np.inf]
PHASE_LABELS = ["opening (1-10)", "middlegame (11-30)", "late (31+)"]

FAMILY_END = {"Game", "Defense", "Opening", "Attack", "Gambit", "System", "Countergambit"}


def setup_style() -> None:
    """Recessive axes and grid, thin marks."""
    plt.rcParams.update({
        "figure.dpi": 120, "savefig.dpi": 150, "savefig.bbox": "tight",
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlecolor": INK,
        "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": INK2, "ytick.color": INK2, "font.size": 9,
        "legend.frameon": False, "lines.linewidth": 2,
    })


def load() -> pd.DataFrame:
    """Rated 3+0 and 5+0 games plus derived columns. Sessions are built over *all* blitz."""
    df = pd.read_parquet(GAMES_TABLE)
    df = df[df["rated"] & (df["time_class"] == "blitz")].copy()
    df = df.sort_values("start_time").reset_index(drop=True)

    # Sessions: built across every blitz control, since a 3+0 game played straight after a 5+0
    # game is still the same sitting.
    new_session = df["start_time"] - df["end_time"].shift() > SESSION_GAP
    df["session_id"] = new_session.cumsum()
    df["session_game_no"] = df.groupby("session_id").cumcount() + 1
    df["session_len"] = df.groupby("session_id")["url"].transform("size")
    df["prev_score"] = df.groupby("session_id")["score"].shift()  # NaN for a session's first game
    # Run of consecutive losses immediately before this game, within the session.
    lost = (df["score"] == 0).astype(int)
    run = lost.groupby((lost != lost.shift()).cumsum()).cumsum() * lost
    df["prev_loss_streak"] = run.groupby(df["session_id"]).shift().fillna(0).astype(int)

    df["local_time"] = df["start_time"].dt.tz_convert(LOCAL_TZ)
    df["hour"] = df["local_time"].dt.hour

    df = df[df["time_control"].isin(CONTROLS)].copy()
    df["tc"] = df["time_control"].map(CONTROLS)
    df["family"] = df["opening"].map(opening_family)
    df["line"] = df["opening"].map(opening_line)
    df["min_clock_frac"] = [min(c) / b if len(c) else np.nan for c, b in zip(df["my_clocks"], df["base_s"])]
    df["time_trouble"] = df["min_clock_frac"] < TIME_TROUBLE_FRAC
    return df


def opening_line(slug: str | None) -> str:
    """Strip move fragments ('3...Nc6', '4.d4') from chess.com's opening slug; keep at most 6 words."""
    if not slug:
        return "Unknown"
    words = [w for w in slug.split() if not re.match(r"^\d+\.", w) and not re.search(r"\d\.", w)]
    return " ".join(words[:6]) or "Unknown"


def opening_family(slug: str | None) -> str:
    """Coarse family: words up to and including the first 'Game/Defense/Opening/...' word."""
    words = opening_line(slug).split()
    for i, w in enumerate(words):
        if w in FAMILY_END:
            return " ".join(words[: i + 1])
    return " ".join(words[:3])


# ----------------------------------------------------------------------------- sections
def results_by_colour(df: pd.DataFrame) -> pd.DataFrame:
    """Win/draw/loss rates by control and colour, with a Wilson CI on the win rate."""
    rows = []
    for (tc, col), g in df.groupby(["tc", "colour"]):
        n = len(g)
        w, d = (g["score"] == 1).sum(), (g["score"] == 0.5).sum()
        lo, hi = wilson_ci(w, n)
        res = residual_summary(g)
        rows.append({"control": tc, "colour": col, "n": n, "win%": 100 * w / n, "draw%": 100 * d / n,
                     "loss%": 100 * (n - w - d) / n, "win% CI": f"{100*lo:.1f}-{100*hi:.1f}",
                     "score": res["score"], "residual": res["residual"],
                     "resid CI": f"{res['ci_lo']:+.3f} to {res['ci_hi']:+.3f}"})
    return pd.DataFrame(rows)


def results_by_rating_gap(df: pd.DataFrame) -> pd.DataFrame:
    """Actual vs expected score by opponent-rating bucket."""
    # Matchmaking keeps ~96% of opponents within ±50 of me, so the buckets are narrow.
    bins = [-np.inf, -50, -20, 20, 50, np.inf]
    labels = ["opp 50+ higher", "opp 20-50 higher", "within 20", "opp 20-50 lower", "opp 50+ lower"]
    # rating_diff = me - opp, so a negative diff means a stronger opponent.
    df = df.assign(gap=pd.cut(df["rating_diff"], bins, labels=labels))
    out = df.groupby(["tc", "gap"], observed=True).apply(residual_summary, include_groups=False)
    return out.reset_index()


def openings(df: pd.DataFrame, level: str, min_n: int) -> pd.DataFrame:
    """Score vs expected per opening (family or line) and colour, for openings with n >= min_n.

    Flagged lines are both in the top-10 most played for that colour and significantly
    below expectation (95% CI on the residual entirely below 0). No multiple-comparison
    correction is applied. Treat the flag as a "look closer" marker, not proof.
    """
    out = (df.groupby(["colour", level]).apply(residual_summary, include_groups=False)
             .reset_index().query("n >= @min_n"))
    out["rank"] = out.groupby("colour")["n"].rank(ascending=False, method="first")
    out["flag"] = np.where((out["rank"] <= 10) & (out["ci_hi"] < 0), "UNDERPERFORMING",
                  np.where(out["ci_lo"] > 0, "strong", ""))
    return out.sort_values(["colour", "n"], ascending=[True, False])


def endings(df: pd.DataFrame) -> pd.DataFrame:
    """How my losses and wins end, with the median and IQR of the move number."""
    df = df.assign(outcome=np.select([df["score"] == 1, df["score"] == 0], ["win", "loss"], "draw"))
    g = df[df["outcome"] != "draw"].groupby(["tc", "outcome", "termination"])
    out = g["n_moves"].describe()[["count", "25%", "50%", "75%"]].reset_index()
    tot = df.groupby(["tc", "outcome"]).size().rename("total")
    out = out.merge(tot, on=["tc", "outcome"])
    out["share%"] = 100 * out["count"] / out["total"]
    return out.drop(columns="total")


def per_move_times(df: pd.DataFrame) -> pd.DataFrame:
    """Long table of my moves: seconds spent and clock remaining, tagged by coarse phase."""
    rows = []
    for tc, base, inc, clocks in zip(df["tc"], df["base_s"], df["increment_s"], df["my_clocks"]):
        prev = base
        for i, c in enumerate(clocks):
            rows.append((tc, i + 1, prev - c + inc, c / base))
            prev = c
    mv = pd.DataFrame(rows, columns=["tc", "move_no", "spent_s", "clock_frac"])
    mv["phase"] = pd.cut(mv["move_no"], PHASE_BINS, labels=PHASE_LABELS)
    return mv


def time_trouble(df: pd.DataFrame) -> pd.DataFrame:
    """Results by whether I dropped below 10% of my base time.

    Restricted to games lasting at least 30 moves. Short games rarely reach time
    trouble, so including them would make "no time trouble" look better through
    selection, not clock skill.
    """
    long = df[df["n_moves"] >= 30]
    out = long.groupby(["tc", "time_trouble"]).apply(residual_summary, include_groups=False).reset_index()
    share = long.groupby("tc")["time_trouble"].agg(["mean", "size"]).reset_index()
    return out, share


def opponent_time_trouble_share(df: pd.DataFrame) -> pd.Series:
    """In games of 30+ moves, how often the opponent was the one below 10%."""
    long = df[df["n_moves"] >= 30]
    opp = [min(c) / b < TIME_TROUBLE_FRAC if len(c) else False for c, b in zip(long["opp_clocks"], long["base_s"])]
    return long.assign(opp_tt=opp).groupby("tc")["opp_tt"].mean()


def session_effects(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Residual by position in the session, by the previous game's result, by loss streak, and by hour."""
    pos_bins = [0, 1, 3, 6, 10, 20, np.inf]
    pos_labels = ["1st", "2-3", "4-6", "7-10", "11-20", "21+"]
    d = df.assign(pos=pd.cut(df["session_game_no"], pos_bins, labels=pos_labels))
    out = {
        "session_position": d.groupby("pos", observed=True).apply(residual_summary, include_groups=False),
        "after_result": df.dropna(subset=["prev_score"]).assign(
            prev=lambda x: x["prev_score"].map({1.0: "after win", 0.5: "after draw", 0.0: "after loss"}))
            .groupby("prev").apply(residual_summary, include_groups=False),
        "loss_streak": df.dropna(subset=["prev_score"]).assign(
            streak=lambda x: x["prev_loss_streak"].clip(upper=3).map({0: "0", 1: "1", 2: "2", 3: "3+"}))
            .groupby("streak").apply(residual_summary, include_groups=False),
        "hour": df.assign(hb=pd.cut(df["hour"], [-1, 5, 9, 13, 17, 21, 23],
                                    labels=["00-05", "06-09", "10-13", "14-17", "18-21", "22-23"]))
            .groupby("hb", observed=True).apply(residual_summary, include_groups=False),
    }
    return out


# ----------------------------------------------------------------------------- charts
def chart_rating(df: pd.DataFrame) -> None:
    """Rating over time per control: monthly median line over faint per-game points."""
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for tc, g in df.groupby("tc"):
        ax.scatter(g["start_time"], g["my_rating"], s=1, color=COLOURS[tc], alpha=0.12, linewidths=0)
        m = g.set_index("start_time")["my_rating"].resample("MS").median().dropna()
        ax.plot(m.index, m.values, color=COLOURS[tc], label=f"{tc} (monthly median)")
        ax.annotate(tc, (m.index[-1], m.values[-1]), xytext=(4, 0), textcoords="offset points",
                    color=INK, va="center", fontsize=9)
    ax.set_title("Blitz rating over time")
    ax.set_ylabel("rating")
    ax.legend(loc="upper left")
    fig.savefig(OUT / "rating_over_time.png")
    plt.close(fig)


def chart_residual_bars(tab: pd.DataFrame, cat: str, title: str, fname: str, by_tc: bool = True) -> None:
    """Horizontal dot-and-whisker plot of residual ± 95% CI, one row per category (and control)."""
    fig, ax = plt.subplots(figsize=(7, 0.35 * len(tab) + 1.2))
    tab = tab.reset_index(drop=False) if cat not in tab.columns else tab
    ylabels, y = [], 0
    for _, r in tab.iterrows():
        colour = COLOURS[r["tc"]] if by_tc else "#2a78d6"
        ax.errorbar(r["residual"], y, xerr=[[r["residual"] - r["ci_lo"]], [r["ci_hi"] - r["residual"]]],
                    fmt="o", color=colour, ms=5, elinewidth=1.5, capsize=0)
        ylabels.append(f"{r['tc'] + '  ' if by_tc else ''}{r[cat]}  (n={int(r['n'])})")
        y += 1
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(range(len(ylabels)), ylabels)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("score minus Elo-expected score (points per game), 95% CI")
    ax.set_title(title)
    fig.savefig(OUT / fname)
    plt.close(fig)


def chart_time_use(mv: pd.DataFrame) -> None:
    """Median seconds per move by move number, per control, with an interquartile band."""
    fig, ax = plt.subplots(figsize=(8, 3.4))
    for tc, g in mv[mv["move_no"] <= 60].groupby("tc"):
        q = g.groupby("move_no")["spent_s"].quantile([0.25, 0.5, 0.75]).unstack()
        ax.fill_between(q.index, q[0.25], q[0.75], color=COLOURS[tc], alpha=0.15, linewidth=0)
        ax.plot(q.index, q[0.5], color=COLOURS[tc], label=tc)
    for b in (10, 30):
        ax.axvline(b + 0.5, color=GRID, lw=1, ls="--")
    ax.set_xlabel("my move number")
    ax.set_ylabel("seconds spent (median, IQR band)")
    ax.set_title("Time spent per move")
    ax.legend()
    fig.savefig(OUT / "time_per_move.png")
    plt.close(fig)


def chart_clock_race(df: pd.DataFrame) -> None:
    """Median seconds left on the clock by move number: me (solid) vs opponents (dashed), one panel per control.

    Each move number uses only the games still going at that point, so later moves skew toward long games.
    """
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=False)
    for ax, (tc, g) in zip(axes, df.groupby("tc")):
        for col, ls, label in (("my_clocks", "-", "me"), ("opp_clocks", "--", "opponents")):
            med = [np.median([c[i] for c in g[col] if len(c) > i]) for i in range(45)]
            ax.plot(range(1, 46), med, color=COLOURS[tc], ls=ls, label=label)
        ax.set_title(f"{tc}: clock left by move")
        ax.set_xlabel("move number")
        ax.set_ylabel("median seconds left")
        ax.legend()
    fig.savefig(OUT / "clock_race.png")
    plt.close(fig)


# ----------------------------------------------------------------------------- main
def fmt(df: pd.DataFrame, floatfmt: str = ".3f") -> str:
    return df.to_markdown(index=False, floatfmt=floatfmt)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    setup_style()
    df = load()
    md = [f"# Phase 2 descriptive summary\n\nRated blitz games: {len(df)} "
          f"({', '.join(f'{k}: {v}' for k, v in df['tc'].value_counts().items())}). "
          f"Dates {df['date'].min()} to {df['date'].max()}.\n"
          "Residual = actual score - Elo-expected score (points per game); 0.01 is about 7 Elo.\n"]

    chart_rating(df)
    md += ["## Results by colour", fmt(results_by_colour(df), ".2f")]

    gap = results_by_rating_gap(df)
    chart_residual_bars(gap, "gap", "Score vs expectation by opponent rating", "rating_gap.png")
    md += ["## By rating gap", fmt(gap)]

    for level, min_n in (("family", 100), ("line", 60)):
        op = openings(df, level, min_n)
        md += [f"## Openings by {level} (n >= {min_n}, both controls pooled)", fmt(op.drop(columns="rank"))]
        top = op[op["rank"] <= 8].assign(tc="3+0")  # tc only sets the dot colour here
        if level == "family":
            top = top.assign(**{level: top["colour"].str[0].str.upper() + ": " + top[level]})
            chart_residual_bars(top, level, "Most-played opening families: score vs expectation",
                                "openings.png", by_tc=False)

    md += ["## How games end", fmt(endings(df), ".1f")]

    mv = per_move_times(df)
    chart_time_use(mv)
    chart_clock_race(df)
    phase_time = mv.groupby(["tc", "phase"], observed=True)["spent_s"].agg(["median", "mean", "size"]).reset_index()
    total = mv.groupby(["tc", "phase"], observed=True)["spent_s"].sum()
    phase_time["share_of_time%"] = (100 * total / total.groupby("tc").transform("sum")).values
    md += ["## Time per move by phase", fmt(phase_time, ".2f")]
    tt, share = time_trouble(df)
    md += ["## Time trouble (games of 30+ moves)", fmt(share.rename(columns={"mean": "share_in_trouble"})),
           "Opponent in time trouble share: " + opponent_time_trouble_share(df).round(3).to_string(), "", fmt(tt)]

    sess = session_effects(df)
    for k, tab in sess.items():
        md += [f"## Session: {k}", fmt(tab.reset_index())]
    chart_residual_bars(sess["session_position"].reset_index().assign(tc="3+0"), "pos",
                        "Score vs expectation by game number within session", "session_position.png",
                        by_tc=False)
    s = df.groupby("session_id").size()
    md += [f"Sessions: {len(s)}; median length {s.median():.0f} games; "
           f"{(s >= 10).mean():.0%} of sessions are 10+ games; "
           f"share of games played as game 11+ of a session: {(df['session_game_no'] > 10).mean():.0%}"]

    (OUT / "summary.md").write_text("\n\n".join(md) + "\n")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
