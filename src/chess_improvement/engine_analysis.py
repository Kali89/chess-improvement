"""Phase 3c: break down my engine-classified errors, and compare them with my opponents'.

Currency: *expected score lost per game* = sum of win-probability drops on my moves (in a
category) / number of games. Within a game, my total drops minus my opponent's roughly add up
to the result relative to the start, so this is in the same units as score. Near 50%, 0.01
points per game is about 7 rating points.

My opponents are the natural baseline. They're rated the same as me (matchmaking keeps them
within ±50), so "me minus opponents" in a category shows where I'm worse than my peers. The raw
volume shows where most of my points leak.

Outputs: reports/phase3/*.png, reports/phase3/tables.md, reports/phase3/instructive.csv

Run:  uv run python -m chess_improvement.engine_analysis
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import DATA_DIR, GAMES_TABLE, REPORTS_DIR
from .descriptive import COLOURS, GRID, INK, INK2, setup_style
from .engine import DEPTH
from .errors import CLOCK_LABELS, EVAL_LABELS
from .stats import wilson_ci

OUT = REPORTS_DIR / "phase3"
ELO_PER_POINT = 1600 / np.log(10)  # ≈ 695 Elo per 1.0 points per game, near 50%
ME, OPP = "#2a78d6", "#eb6834"     # here blue/orange mean me vs opponents (the charts say so)


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    plies = pd.read_parquet(DATA_DIR / "processed" / f"plies_d{DEPTH}.parquet")
    games = pd.read_parquet(GAMES_TABLE).set_index("url").loc[plies["url"].unique()]
    return plies, games.reset_index()


def rate_table(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Mistake+blunder rate per 100 moves, and blunder rate, with Wilson CIs. Me and opponents side by side."""
    rows = []
    for keys, g in df.groupby(by + ["is_me"], observed=True):
        keys = keys if isinstance(keys, tuple) else (keys,)
        n, k, b = len(g), int(g["is_error"].sum()), int((g["severity"] == "blunder").sum())
        lo, hi = wilson_ci(k, n)
        rows.append(dict(zip(by + ["who"], list(keys[:-1]) + ["me" if keys[-1] else "opp"]),
                         moves=n, errors=k, err_per_100=100 * k / n, ci=f"{100*lo:.1f}-{100*hi:.1f}",
                         blunders_per_100=100 * b / n))
    return pd.DataFrame(rows)


def cost_table(df: pd.DataFrame, by: str, n_games: int) -> pd.DataFrame:
    """Points (expected score) lost per 100 games to mistakes+blunders, by category, me vs opponents.

    Columns:
        me / opp       : points per 100 games given away in this category
        share%         : this category's share of all the points I give away through errors
        excess_elo     : (me - opp) per game x ~695. The rating gap this category alone would open
                         between me and an otherwise-identical peer. Only differences get an Elo
                         figure: absolute volumes aren't rating points, because both players give
                         points away all game.
    """
    e = df[df["is_error"]]
    t = (e.groupby([by, "is_me"], observed=True)["wp_loss"].sum().unstack("is_me").fillna(0) / n_games)
    t = t.rename(columns={True: "me", False: "opp"})
    t["excess_elo"] = (t["me"] - t["opp"]) * ELO_PER_POINT
    t["share%"] = 100 * t["me"] / t["me"].sum()
    t[["me", "opp"]] *= 100
    cnt = e[e["is_me"]].groupby(by, observed=True).size().rename("my_errors")
    return t.join(cnt).sort_values("me", ascending=False).reset_index()


def bootstrap_ci(df: pd.DataFrame, by: str, cat: str, n_boot: int = 500, seed: int = 0) -> tuple[float, float]:
    """Game-level bootstrap 95% CI for my points lost per 100 games in one category."""
    e = df[df["is_error"] & df["is_me"] & (df[by] == cat)].groupby("url")["wp_loss"].sum()
    per_game = e.reindex(df["url"].unique(), fill_value=0).to_numpy()
    rng = np.random.default_rng(seed)
    boots = rng.choice(per_game, (n_boot, len(per_game))).mean(axis=1) * 100
    return tuple(np.percentile(boots, [2.5, 97.5]))


def clock_link(plies: pd.DataFrame, games: pd.DataFrame) -> dict:
    """What the clock costs, net of what it wins.

    Flagging cost: in a timeout loss, my win probability at my last move is what I'd otherwise have
    expected to score, so it counts as points given to the clock. Symmetrically, in a timeout win
    my opponent's last win probability is a gift. The net balance per 100 games, converted to Elo,
    is the rating effect of the clock alone (it's a difference, so the Elo conversion is fair).
    """
    last = plies.sort_values("ply").groupby(["url", "is_me"]).tail(1).set_index(["url", "is_me"])["wp_after"]
    g = games.set_index("url")
    n = len(g)
    lost_on_time = g.index[(g["score"] == 0) & (g["termination"] == "timeout")]
    won_on_time = g.index[(g["score"] == 1) & (g["termination"] == "timeout")]
    my_last = last.xs(True, level="is_me").reindex(lost_on_time).dropna()
    opp_last = last.xs(False, level="is_me").reindex(won_on_time).dropna()
    me = plies[plies["is_me"]]
    opp = plies[~plies["is_me"]]
    net = (my_last.sum() - opp_last.sum()) / n
    return {
        "n_games": n,
        "I lost on time": len(my_last),
        "  ...from winning (>70%)": int((my_last > 0.7).sum()),
        "  ...from level (30-70%)": int(my_last.between(0.3, 0.7).sum()),
        "I won on time": len(opp_last),
        "  ...opp was winning (>70%)": int((opp_last > 0.7).sum()),
        "points I lose to flagging per 100 games": 100 * my_last.sum() / n,
        "points I win by opp flagging per 100 games": 100 * opp_last.sum() / n,
        "net clock effect in Elo (negative = costs me)": -net * ELO_PER_POINT,
        "share of my moves made under 10% clock": (me["clock_frac"] < 0.10).mean(),
        "share of opp moves made under 10% clock": (opp["clock_frac"] < 0.10).mean(),
        "share of my errors made under 10% clock": (me.loc[me["is_error"], "clock_frac"] < 0.10).mean(),
    }


def instructive(plies: pd.DataFrame, k: int = 40) -> pd.DataFrame:
    """Candidate study positions: clear errors in live positions with time on the clock, one per game.

    - wp_before 0.25-0.85: the game was still undecided, so the error changed it
    - wp_loss >= 0.30: a blunder
    - clock >= 15%: not a pure scramble, so the position is solvable at the board
    - at most one per game (the worst), to avoid one disaster dominating the list
    The report step re-verifies these at higher depth with two candidate moves.
    """
    c = plies[plies["is_me"] & plies["wp_before"].between(0.25, 0.85) & (plies["wp_loss"] >= 0.30)
              & (plies["clock_frac"] >= 0.15) & plies["theme"].notna()]
    c = c.sort_values("wp_loss", ascending=False).groupby("url").head(1)
    cols = ["url", "tc", "move_no", "fen", "played_san", "best_san", "best_pv", "wp_before", "wp_after",
            "wp_loss", "theme", "error_kind", "phase", "clock_frac"]
    return c[cols].head(k * 3)


# ----------------------------------------------------------------------------- charts
def chart_me_vs_opp(tab: pd.DataFrame, cat: str, order: list[str], title: str, fname: str) -> None:
    """Grouped horizontal bars: errors per 100 moves, me vs opponents, with CI whiskers."""
    fig, ax = plt.subplots(figsize=(7, 0.55 * len(order) + 1.3))
    h = 0.36
    for j, (who, colour, label) in enumerate([("me", ME, "me"), ("opp", OPP, "opponents")]):
        t = tab[tab["who"] == who].set_index(cat).reindex(order)
        y = np.arange(len(order)) + (j - 0.5) * (h + 0.04)
        lo = t["ci"].str.split("-").str[0].astype(float)
        hi = t["ci"].str.split("-").str[1].astype(float)
        ax.barh(y, t["err_per_100"], height=h, color=colour, label=label)
        ax.errorbar(t["err_per_100"], y, xerr=[t["err_per_100"] - lo, hi - t["err_per_100"]],
                    fmt="none", ecolor=INK2, elinewidth=1)
    ax.set_yticks(np.arange(len(order)),
                  [f"{o}  (n={int(tab[(tab[cat] == o) & (tab['who'] == 'me')]['moves'].sum())})" for o in order])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("mistakes + blunders per 100 moves (95% CI)")
    ax.set_title(title)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2)
    fig.savefig(OUT / fname)
    plt.close(fig)


def chart_cost(cost: pd.DataFrame, cat: str, title: str, fname: str) -> None:
    """Rating points per game leaking through each category, me vs opponents."""
    order = cost[cat].tolist()
    fig, ax = plt.subplots(figsize=(7, 0.55 * len(order) + 1.3))
    h = 0.36
    y = np.arange(len(order))
    ax.barh(y - 0.2, cost["me"], height=h, color=ME, label="me")
    ax.barh(y + 0.2, cost["opp"], height=h, color=OPP, label="opponents")
    for yi, v in zip(y, cost["me"]):
        ax.annotate(f"{v:.0f}", (v, yi - 0.2), xytext=(3, 0), textcoords="offset points", va="center",
                    color=INK, fontsize=8)
    ax.set_yticks(y, [f"{o}  (n={int(n)})" for o, n in zip(order, cost["my_errors"].fillna(0))])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("points given away per 100 games (mistakes + blunders)")
    ax.set_title(title)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2)
    fig.savefig(OUT / fname)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    setup_style()
    plies, games = load()
    n_games = plies["url"].nunique()
    md = [f"# Phase 3 engine tables\n\n{n_games} games, {int(plies['is_me'].sum())} of my moves, "
          f"Stockfish depth {DEPTH}. Errors = mistakes + blunders (win-prob drop >= 20 points).\n"]

    md += ["## Overall error rates", rate_table(plies, ["tc"]).to_markdown(index=False, floatfmt=".2f")]
    for cat, order, title, fname in [
        ("phase", ["opening", "middlegame", "endgame"], "Errors by game phase", "errors_by_phase.png"),
        ("clock_bucket", CLOCK_LABELS[::-1], "Errors by clock remaining (share of base time)", "errors_by_clock.png"),
        ("eval_bucket", EVAL_LABELS, "Errors by position before the move (my win probability)", "errors_by_eval.png"),
    ]:
        t = rate_table(plies, [cat])
        chart_me_vs_opp(t, cat, order, title, fname)
        md += [f"## By {cat}", t.to_markdown(index=False, floatfmt=".2f"),
               rate_table(plies, ["tc", cat]).to_markdown(index=False, floatfmt=".2f")]

    eg = plies[plies["phase"] == "endgame"]
    md += ["## Endgames by material type", rate_table(eg, ["endgame_type"]).to_markdown(index=False, floatfmt=".2f")]

    theme_cost = cost_table(plies, "theme", n_games)
    theme_cost["me_ci"] = [
        "{:.0f}-{:.0f}".format(*bootstrap_ci(plies, "theme", t)) for t in theme_cost["theme"]]
    chart_cost(theme_cost, "theme", "Where the points go: error themes", "cost_by_theme.png")
    md += ["## Cost by theme (points lost per 100 games; me_ci = game-bootstrap 95% CI)",
           theme_cost.to_markdown(index=False, floatfmt=".3f")]
    for by in ("error_kind", "phase", "clock_bucket", "eval_bucket"):
        md += [f"## Cost by {by}", cost_table(plies, by, n_games).to_markdown(index=False, floatfmt=".3f")]
    eg_cost = cost_table(eg, "endgame_type", n_games)
    md += ["## Endgame cost by type", eg_cost.to_markdown(index=False, floatfmt=".3f")]

    mine = plies[plies["is_me"] & plies["is_error"]]
    md += ["## Theme x clock (my errors, counts)",
           pd.crosstab(mine["theme"], mine["clock_bucket"]).to_markdown(),
           "## Theme x phase (my errors, counts)", pd.crosstab(mine["theme"], mine["phase"]).to_markdown()]
    md += ["## Clock link", pd.Series(clock_link(plies, games)).to_markdown()]

    inst = instructive(plies)
    inst.to_csv(OUT / "instructive_candidates.csv", index=False)
    md += [f"## Instructive candidates: {len(inst)} (see instructive_candidates.csv)",
           inst["theme"].value_counts().to_markdown()]
    (OUT / "tables.md").write_text("\n\n".join(md) + "\n")
    print("\n\n".join(md))


if __name__ == "__main__":
    main()
