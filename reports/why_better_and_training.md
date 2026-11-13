# Why I'm at my peak, and how to keep improving

*Written 2026-11-13. Rating 1489 blitz (all-time high). Builds on [report.md](report.md). New analyses: a
300-game engine sample from Aug 2025–Mar 2026 for comparison ([then_vs_now.md](then_vs_now.md)), a rolling
"burst" analysis of my rating history, and a profile of how I miss threats ([threat_profile.md](threat_profile.md)).*

## Part 1: What actually shifted

### The short version

My rating has risen in **two stages**, and only the first is a stable change.

1. **Mid-2026: my 5+0 strength stepped up by about 60–75 points.** My 3+0 strength did not move at all.
2. **The last 10 days: a +200 hot streak at 5+0**, the biggest in my history. Some of it will last; most of it probably won't.

My best estimate of my *current underlying strength* is **about 1340–1380 at 5+0** and **about 1250 at 3+0**. The 1489 on the screen is above both, so **expect the rating to drift back down even if I keep improving**. That will be regression, not getting worse.

### Evidence

**3+0 has been flat for three years.** I measured performance per half-year as rating plus the score-vs-expected adjustment. That's a performance rating that doesn't depend on which control the rating pool happened to be fed by.

| | 2023 H2 | 2024 H1 | 2024 H2 | 2025 H1 | 2025 H2 | 2026 H1 | 2026 H2 |
|---|---|---|---|---|---|---|---|
| **3+0** | 1247 ± 25 | 1269 ± 26 | 1266 ± 22 | 1224 ± 40 | 1250 ± 26 | 1251 ± 23 | 1253 ± 33 |
| **5+0** | 1328 ± 49 | 1327 ± 29 | 1234 ± 45 | 1286 ± 56 | 1239 ± 28 | (5 games) | **1379 ± 40** |

**At 5+0, the step came before the streak.** In July–October 2026 I performed at **1323 ± 48** at 5+0, against 1245 ± 22 over the previous two years. That was *before* November.

**The streak (2–12 November, 114 games, 96 of them at 5+0) performed at about 1490 ± 66.** Its score was 0.627 against an expected 0.501, against opponents averaging 1386. Measured against the 500 games before it, this burst is **+200, the largest in my history** (above the 99.99th percentile of rolling 114-game windows). I've had smaller ones before, and each mostly faded:

| Burst ended | Burst size | Next 200 games vs. pre-burst level |
|---|---|---|
| Sep 2022 | +138 | +9 |
| Apr 2023 | +138 | +107 |
| Feb 2024 | +169 | +74 |
| Sep 2025 | +195 | +66 |
| May 2026 | +152 | +51 |
| **Nov 2026** | **+200** | ? |

So historically I keep about a third of a burst. Applied here, that gives roughly 1274 + 65 ≈ 1340. Pooling the July–October level with the streak instead, weighted by their precision, gives about 1380. Hence the 1340–1380 range.

**The streak wasn't my opponents handing me games.** The engine shows they made a normal number of errors (5.9 per 100 moves, against 5.7 before and 6.5 recently), even though they were stronger. *I* played cleaner: 2.7 blunders per 100 moves, against 3.8 in July–October. One caveat: the streak was picked out *because* it went well, so it's bound to look clean. That tells us *how* I won (fewer blunders), not that the form will last.

**What it wasn't:**
- **The opening switch.** I moved from the Scandinavian (1…d5) to 1…e5 as Black in late 2024 and early 2025, 18 months before the rise. 1…e5 has scored slightly *below* the Scandinavian (−0.027 vs expectation, n = 938).
- **Tilt or session patterns.** No change, and no tilt effect in either period.
- **Volume.** About the same games per day, except during the streak itself (11 a day against 5–6).

### What *has* been improving: attacking

The cleanest long-run trend in the engine data is in **missed chances**, compared with same-rated opponents in the same games. Negative means I miss fewer chances than they do:

| | Aug 2025–Mar 2026 | Jul–Oct 2026 | Nov streak |
|---|---|---|---|
| Missed chances, me minus opponents | −15 Elo (−41 to +14) | −35 (−66 to −4) | −56 (−99 to −13) |
| Missed threats, me minus opponents | +1 (−40 to +42) | **+61 (+25 to +96)** | +20 (−61 to +102) |

My **attacking vision is getting better** and is now a clear strength. My **defensive vision hasn't kept up, and recently looks worse**. Neither trend is individually significant between periods, but they point in a consistent direction. That defensive gap is now the largest thing standing between me and the next 100 points.

### Why 5+0 and not 3+0?

Fast tactical vision only pays off if there's time to use it. At 3+0 I fall about 25 seconds behind my opponent by move 30 and lose 60 games in 300 on time (19 of them from winning positions). Whatever improved this year, 3+0 doesn't let it show. **Playing more 5+0 is part of why my rating went up.** It isn't a trick: it's where I'm actually stronger.

---

## Part 2: Exactly what to work on

### Weakness 1: grabbing pawns without checking the consequences

Across 897 engine-analysed games (about 30,000 of my moves and 30,000 of my opponents'), **almost all of my excess threat-blindness compared with my opponents happens at one kind of moment**:

| My move was... | How often it allowed a tactic: me | Opponents |
|---|---|---|
| **capturing a pawn** | **4.6%** (3.9–5.3), n = 3,508 | 3.1% (2.5–3.8), n = 2,993 |
| — of which in the **middlegame** | **7.1%** (5.8–8.8), n = 1,162, about **1 in 14** | |
| capturing a piece | 1.3% | 1.2% |
| any non-capture | 2.85% | 2.78% |

I also grab pawns about 17% more often than my opponents. Piece captures and quiet moves are no worse than my peers'. **The leak is specifically taking pawns:** greed plus a missing safety check. A typical example is the poisoned b2 pawn, as in my most recent game (11…Qxb2?, 50% → 25%).

**Related patterns, smaller and also above my opponents:**
- **The punishing reply is often a check** (0.81 vs 0.64 per 100 moves). Taking a pawn often lets a piece or the opponent's king-side attack in with check.
- **Mistakes straight after the opponent checks me** (69 vs 37). After a check I play the forced-looking move without re-scanning.
- **Rook moves** (0.59 vs 0.40 per 100 moves). Usually a rook leaving the back rank or giving up the defence of something.
- **Back-rank mates:** 20 of the 77 mates I allowed, against 11 for my opponents.

### Weakness 2: 3+0 clock management

Unchanged from the main report: I'm 24 Elo weaker at 3+0, with a net loss of about 51 Elo to flagging. For now the answer is mostly **to play 5+0** (see the plan).

### Not worth working on now

Endgame theory (on par with my peers), opening theory in general (on par; the Italian as White is a strength at +0.09 since 2025), and tilt (none).

---

## Part 3: The training regime

**Budget:** about 100 minutes a week, plus a few seconds' habit during games.
**Principle:** work on one in-game habit at a time, and get feedback on it from my own games every session, not just puzzles in general.

### The tools (all in this repo)

| Tool | When | What it does |
|---|---|---|
| `uv run python -m chess_improvement.review` | **After every sitting** (about 1 min of compute, 5 min of reading) | Engine-checks the games just played and lists each mistake as *missed THEIR threat* or *missed MY chance*. Pawn grabs get a ⚠ flag. It prints a session scorecard against my baseline, logs it to `data/drills/review_log.csv`, and adds clean new positions to the drill deck. |
| `uv run python -m chess_improvement.drill` | 3 × 10 min a week | Spaced-repetition trainer on **my own** mistakes (85 positions to start, 29 of them pawn grabs). It shows my opponent's last move and asks me to name their threat before I answer. Stockfish grades the move. Missed drills come back the next day; passed ones come back after 3, 7, 16 and 35 days. `--pawn-grabs` restricts it to pawn-grab positions; `--stats` shows pass rates. |
| `uv run python -m chess_improvement.progress --since 2026-11-13` | Monthly | Before/after comparison on all tracked metrics, with CIs. |

### In-game habits, introduced one at a time

Each habit gets two weeks before the next is added. A habit is "in" when I do it without thinking. The post-session review shows whether I did.

| Weeks | Habit | The exact trigger and question |
|---|---|---|
| **1–2** | **The pawn rule** | **Trigger:** I'm about to capture a pawn in the middlegame. **Question:** "After I take, what are their checks, and which of my pieces become loose?" Take only once I've answered. Costs about 3 seconds, a few times a game. |
| **3–4** | **+ the check rule** | **Trigger:** my opponent has just given check, or my move allows a check. **Question:** "After this check, what does their *next* move do?" Don't autopilot the reply. |
| **5–6** | **+ the rook/back-rank rule** | **Trigger:** moving a rook off my back rank, or both sides have heavy pieces on. **Question:** "What was this rook guarding? Does my king need luft (h3/h6)?" |
| **7+** | **Reintroduce 3+0** if wanted, with **clock checkpoints** | Aim for ≥ 120 s at move 20 and ≥ 75 s at move 30. When winning with < 30 s left: trade pieces and keep everything defended. |

**Time control while building habits: play 5+0** (or 10+0). I'm 24–48 Elo stronger there, and habits need thinking time before they become automatic. Keep sittings to about 5 games, so that `review` stays a 5-minute job.

### Weekly study schedule (about 100 min)

| Session | Minutes | Content |
|---|---|---|
| **Post-session reviews** | 4 × 5 = 20 | `review` after each sitting. For every "missed THEIR threat", write one line in a notebook: *the threat was ___; the question that would have caught it was ___.* |
| **Own-positions drill** | 3 × 10 = 30 | `drill` (8 positions each time). In weeks 1–2, do one of the three sessions with `--pawn-grabs`. |
| **Defensive pattern puzzles** | 2 × 15 = 30 | Lichess themes chosen to match my profile: [Defensive move](https://lichess.org/training/defensiveMove) every time, plus one of: [Back-rank mate](https://lichess.org/training/backRankMate) (20 allowed back-rank mates), [Exposed king](https://lichess.org/training/exposedKing) (punishing replies are often checks), [Intermezzo](https://lichess.org/training/intermezzo) (in-between moves during captures). **Method:** before solving, say what the *side not to move* is threatening. |
| **Slow game** | 20 | One 10+0 game, using the current habit on *every* qualifying move. |

**Once a month (20 min): repair one opening line.** In priority order:
1. **As White against 1…g6, the Modern** (−0.15 since 2025, n = 69). Pick one setup (e.g. e4, d4, Nc3, Be3, Qd2) and play it every time.
2. **As Black against the Scotch, 4.Nxd4** (−0.09, n = 56).
3. **As Black against the King's Gambit** (−0.08, n = 56).

Use the lichess opening explorer to learn the main line to move 8. Each line costs only about 1 Elo overall, so this is low priority and done once.

### How I'll know it's working

1. **Each session:** the `review` scorecard. Target **missed threats per game ≤ 0.7** (baseline 1.03). Single sessions are noisy, so watch the trend in `review_log.csv` over 10+ sessions.
2. **The drill deck:** `drill --stats`. Pass rates on "allowed tactic" and "hung piece" drills should rise, and positions should move up to box 3+.
3. **Monthly:** `progress --since 2026-11-13`. The primary metric is **middlegame pawn grabs that allowed a tactic: baseline 7.1% (5.8–8.8), target ≤ 5%**. Secondary: missed threats per game, blunders per 100 moves (3.6), and the share of moves made under 10% clock.
4. **Rating: ignore it for 4–6 weeks.** It will probably fall from 1489 toward about 1380 as the streak regresses, and that's not evidence of anything. Judge by the metrics above. After 6 weeks, the bar is 5+0 performance staying above 1340 *while* the habit metrics improve.
