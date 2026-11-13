# How I miss threats (me vs my opponents, same games)


862 of my missed-threat errors, 790 of my opponents', in 897 games.


## The punishing reply

| reply   |   me |   opp |   me /100 moves |   opp /100 moves |
|:--------|-----:|------:|----------------:|-----------------:|
| capture |  358 |   337 |            1.18 |             1.11 |
| check   |  246 |   195 |            0.81 |             0.64 |
| quiet   |  258 |   258 |            0.85 |             0.85 |

## My mistaken move was a...

| my_move   |   me |   opp |   me /100 moves |   opp /100 moves |
|:----------|-----:|------:|----------------:|-----------------:|
| capture   |  213 |   140 |            0.7  |             0.46 |
| check     |   31 |    29 |            0.1  |             0.1  |
| quiet     |  618 |   621 |            2.04 |             2.05 |

## Reply is a fork

| fork   |   me |   opp |   me /100 moves |   opp /100 moves |
|:-------|-----:|------:|----------------:|-----------------:|
| False  |  672 |   611 |            2.22 |             2.02 |
| True   |  190 |   179 |            0.63 |             0.59 |

## The piece I just moved is the one taken

| victim_is_moved_piece   |   me |   opp |   me /100 moves |   opp /100 moves |
|:------------------------|-----:|------:|----------------:|-----------------:|
| False                   |  683 |   632 |            2.25 |             2.09 |
| True                    |  179 |   158 |            0.59 |             0.52 |

## Mistake came right after the opponent captured

| after_opp_capture   |   me |   opp |   me /100 moves |   opp /100 moves |
|:--------------------|-----:|------:|----------------:|-----------------:|
| False               |  655 |   602 |            2.16 |             1.99 |
| True                |  207 |   188 |            0.68 |             0.62 |

## Mistake came right after a check

| after_opp_check   |   me |   opp |   me /100 moves |   opp /100 moves |
|:------------------|-----:|------:|----------------:|-----------------:|
| False             |  793 |   753 |            2.62 |             2.48 |
| True              |   69 |    37 |            0.23 |             0.12 |

## My move grabbed a pawn

| pawn_grab   |   me |   opp |   me /100 moves |   opp /100 moves |
|:------------|-----:|------:|----------------:|-----------------:|
| False       |  703 |   697 |            2.32 |             2.3  |
| True        |  159 |    93 |            0.52 |             0.31 |

## Piece I moved

| moved_piece   |   me |   opp |   me /100 moves |   opp /100 moves |
|:--------------|-----:|------:|----------------:|-----------------:|
| bishop        |  143 |   120 |            0.47 |             0.4  |
| king          |   87 |    81 |            0.29 |             0.27 |
| knight        |  137 |   147 |            0.45 |             0.49 |
| pawn          |  172 |   186 |            0.57 |             0.61 |
| queen         |  143 |   134 |            0.47 |             0.44 |
| rook          |  180 |   122 |            0.59 |             0.4  |

## Phase

| phase      |   me |   opp |   me /100 moves |   opp /100 moves |
|:-----------|-----:|------:|----------------:|-----------------:|
| endgame    |  157 |   120 |            0.52 |             0.4  |
| middlegame |  597 |   545 |            1.97 |             1.8  |
| opening    |  108 |   125 |            0.36 |             0.41 |

## Allowed mates: back-rank pattern

| back_rank_mate   |   me |   opp |
|:-----------------|-----:|------:|
| False            |   57 |    33 |
| True             |   20 |    11 |
