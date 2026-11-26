3)
a)
| N | reference (seed: 1, 2, 3) | drifted (seed: 1, 2, 3) |
| --- | --- | --- |
| 100 | 0.1493, 0.3666, 0.1735 | 0.4700, 0.2957, 0.3628 |
| 300 | 0.1141, 0.1891, 0.1475 | 0.3887, 0.2858, 0.2951 |
| 500 | 0.1263, 0.1834, 0.1400 | 0.3657, 0.2826, 0.3886 |
| 800 | 0.1194, 0.2329, 0.1511 | 0.3611, 0.3234, 0.3363 |

b)
- threshold: 0.235, min_samples: 500
- sorok: N=100-nál még átfedés van (reference: 0.3666, drifted: 0.2957), N=500-on (reference max 0.1834, drifted min 0.2826) és N=800-on (reference max 0.2329, drifted min 0.3234)

c) INSUFFICIENT: nincs elég sor az ellenőrzéshez
NO_DRIFT: elegendő sor alapján egyik gated feature sem lépte át a küszöböt.

4)
a)
- Metric: roc_auc.
- F1: az F1 score függ a pozitív osztály arányától.

b)
| Case | Your numbers | What you would do |
| --- | --- | --- |
| drift and degradation | glucose PSI = 0.2506 (> 0.235), roc_auc: 0.8761 -> 0.8265 | Rollback az előző modellverzióra |
| drift, no degradation | nem volt ilyen eset | Elmozdult feature és upstream változás ellenőrzése, nem feltétlen kell rollback. |
| degradation, no drift | nem volt ilyen eset | Drift vizsgálata címkézett adaton, modell újratanítása vagy kivonása. |
