# Then vs now: engine-measured play by period


Rates are per 100 moves with 95% Wilson CIs. 'me minus opp' is points lost per game converted to Elo (positive = I gave away more than my opponent), with a game-bootstrap CI.


## both controls

|                                    | before           | recent           | streak            |
|:-----------------------------------|:-----------------|:-----------------|:------------------|
| games                              | 302              | 477              | 113               |
| mean opp rating                    | 1228             | 1273             | 1386              |
| score                              | 0.507            | 0.493            | 0.624             |
| my errors /100 moves               | 5.8 (5.3-6.2)    | 6.5 (6.1-6.8)    | 5.2 (4.6-5.9)     |
| opp errors /100 moves              | 5.7 (5.3-6.2)    | 6.5 (6.1-6.9)    | 5.9 (5.2-6.7)     |
| my blunders /100                   | 3.2 (2.9-3.6)    | 3.8 (3.5-4.1)    | 2.7 (2.3-3.3)     |
| opp blunders /100                  | 3.3 (3.0-3.7)    | 3.8 (3.5-4.1)    | 3.2 (2.7-3.8)     |
| my missed threats /100             | 2.5 (2.2-2.9)    | 3.1 (2.8-3.4)    | 2.6 (2.2-3.1)     |
| opp missed threats /100            | 2.6 (2.3-2.9)    | 2.7 (2.5-3.0)    | 2.3 (1.9-2.8)     |
| my missed chances /100             | 0.7 (0.6-0.9)    | 1.0 (0.9-1.2)    | 0.4 (0.3-0.7)     |
| opp missed chances /100            | 0.8 (0.6-1.0)    | 1.3 (1.1-1.4)    | 0.9 (0.7-1.2)     |
| my errors /100 with >50% clock     | 5.9 (5.4-6.5)    | 5.5 (5.1-6.0)    | 5.2 (4.4-6.1)     |
| opp errors /100 with >50% clock    | 6.1 (5.5-6.6)    | 6.3 (5.9-6.8)    | 5.9 (5.1-6.8)     |
| % my moves under 10% clock         | 5.8 (5.3-6.2)    | 7.2 (6.8-7.6)    | 8.4 (7.5-9.2)     |
| % opp moves under 10% clock        | 4.0 (3.6-4.4)    | 3.8 (3.5-4.1)    | 6.3 (5.6-7.1)     |
| me minus opp, all errors (Elo)     | -3 (-38 to +33)  | +12 (-14 to +38) | -78 (-132 to -25) |
| me minus opp, missed threats (Elo) | +1 (-40 to +42)  | +61 (+25 to +96) | +20 (-61 to +102) |
| me minus opp, missed chances (Elo) | -15 (-41 to +14) | -35 (-66 to -4)  | -56 (-99 to -13)  |

## 5+0

|                                    | before           | recent           | streak            |
|:-----------------------------------|:-----------------|:-----------------|:------------------|
| games                              | 152              | 195              | 95                |
| mean opp rating                    | 1218             | 1285             | 1402              |
| score                              | 0.559            | 0.554            | 0.626             |
| my errors /100 moves               | 5.9 (5.3-6.6)    | 6.3 (5.8-6.9)    | 5.4 (4.7-6.2)     |
| opp errors /100 moves              | 5.8 (5.2-6.5)    | 6.3 (5.7-6.9)    | 5.9 (5.2-6.8)     |
| my blunders /100                   | 3.1 (2.7-3.7)    | 3.5 (3.1-4.0)    | 2.7 (2.2-3.3)     |
| opp blunders /100                  | 3.2 (2.8-3.8)    | 3.6 (3.1-4.0)    | 3.1 (2.6-3.8)     |
| my missed threats /100             | 2.6 (2.2-3.1)    | 3.1 (2.7-3.6)    | 2.7 (2.2-3.3)     |
| opp missed threats /100            | 2.5 (2.1-3.0)    | 2.6 (2.3-3.0)    | 2.4 (1.9-2.9)     |
| my missed chances /100             | 0.7 (0.5-1.0)    | 0.9 (0.7-1.1)    | 0.4 (0.2-0.7)     |
| opp missed chances /100            | 1.0 (0.7-1.3)    | 1.3 (1.0-1.6)    | 0.8 (0.6-1.2)     |
| my errors /100 with >50% clock     | 5.9 (5.2-6.7)    | 5.9 (5.3-6.6)    | 5.4 (4.5-6.4)     |
| opp errors /100 with >50% clock    | 6.2 (5.5-7.0)    | 6.0 (5.4-6.7)    | 6.0 (5.1-7.0)     |
| % my moves under 10% clock         | 3.6 (3.1-4.2)    | 4.4 (3.9-4.9)    | 7.7 (6.9-8.7)     |
| % opp moves under 10% clock        | 4.6 (4.0-5.2)    | 4.1 (3.6-4.6)    | 6.1 (5.4-7.0)     |
| me minus opp, all errors (Elo)     | -7 (-58 to +42)  | +7 (-34 to +48)  | -63 (-117 to -5)  |
| me minus opp, missed threats (Elo) | +20 (-33 to +75) | +63 (+5 to +118) | +19 (-62 to +107) |
| me minus opp, missed chances (Elo) | -37 (-72 to -1)  | -55 (-99 to -14) | -41 (-90 to +4)   |

## 3+0

|                                    | before           | recent            | streak             |
|:-----------------------------------|:-----------------|:------------------|:-------------------|
| games                              | 150              | 282               | 18                 |
| mean opp rating                    | 1237             | 1264              | 1300               |
| score                              | 0.453            | 0.450             | 0.611              |
| my errors /100 moves               | 5.6 (5.0-6.3)    | 6.5 (6.1-7.1)     | 4.2 (2.9-5.9)      |
| opp errors /100 moves              | 5.7 (5.1-6.4)    | 6.7 (6.2-7.2)     | 5.8 (4.3-7.8)      |
| my blunders /100                   | 3.3 (2.9-3.9)    | 4.1 (3.7-4.5)     | 3.0 (2.0-4.6)      |
| opp blunders /100                  | 3.4 (2.9-3.9)    | 3.9 (3.5-4.3)     | 3.8 (2.6-5.4)      |
| my missed threats /100             | 2.4 (2.1-2.9)    | 3.1 (2.8-3.5)     | 2.3 (1.4-3.7)      |
| opp missed threats /100            | 2.7 (2.3-3.2)    | 2.8 (2.4-3.1)     | 2.2 (1.3-3.5)      |
| my missed chances /100             | 0.7 (0.5-1.0)    | 1.1 (0.9-1.4)     | 0.4 (0.1-1.3)      |
| opp missed chances /100            | 0.6 (0.4-0.8)    | 1.2 (1.0-1.5)     | 1.3 (0.7-2.5)      |
| my errors /100 with >50% clock     | 5.8 (5.1-6.7)    | 5.2 (4.7-5.8)     | 3.9 (2.3-6.4)      |
| opp errors /100 with >50% clock    | 5.9 (5.2-6.7)    | 6.6 (6.0-7.2)     | 5.6 (3.9-8.1)      |
| % my moves under 10% clock         | 7.9 (7.2-8.7)    | 9.2 (8.6-9.8)     | 11.5 (9.4-14.1)    |
| % opp moves under 10% clock        | 3.4 (2.9-3.9)    | 3.6 (3.3-4.0)     | 7.1 (5.4-9.2)      |
| me minus opp, all errors (Elo)     | +2 (-44 to +52)  | +15 (-20 to +51)  | -157 (-293 to -11) |
| me minus opp, missed threats (Elo) | -19 (-79 to +42) | +59 (+13 to +105) | +22 (-174 to +191) |
| me minus opp, missed chances (Elo) | +8 (-33 to +52)  | -22 (-66 to +20)  | -130 (-231 to -37) |
