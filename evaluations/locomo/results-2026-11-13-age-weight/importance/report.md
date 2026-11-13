## Cue coverage (session-written cues, cues.json.gz, deepseek-flash)

- conv-26: 181 cue items sent, write {'written': 181, 'skipped': 0, 'embedded': 181}, rows 181 (with vector 181), stored user messages 419, weight calls {'candidates': 504432, 'tail': 0}
- conv-30: 127 cue items sent, write {'written': 127, 'skipped': 0, 'embedded': 127}, rows 127 (with vector 127), stored user messages 369, weight calls {'candidates': 265008, 'tail': 0}
- conv-41: 237 cue items sent, write {'written': 237, 'skipped': 0, 'embedded': 237}, rows 237 (with vector 237), stored user messages 663, weight calls {'candidates': 595584, 'tail': 0}

| stored user messages | n | with cue |
|---|---|---|
| all | 1451 | 37.6% |
| age under 30 d at +1 d | 275 | 36.4% |
| age 30-90 d at +1 d | 463 | 37.8% |
| age 90-180 d at +1 d | 560 | 37.9% |
| age over 180 d at +1 d | 153 | 37.9% |

| unique evidence turns | n | with cue |
|---|---|---|
| all | 335 | 82.1% |
| age under 30 d at +1 d | 61 | 77.0% |
| age 30-90 d at +1 d | 97 | 81.4% |
| age 90-180 d at +1 d | 137 | 84.7% |
| age over 180 d at +1 d | 40 | 82.5% |

Evidence turn-question pairs with a cue: 450 of 519 (86.7%); questions with at least one cued evidence turn: 338 of 383; with all evidence cued: 319

## Recall per arm

### +1d: all evidence shown % / mean evidence share % (n questions)

| group | n | auto | flat | cued_direct | cued_floor_040 | cued_floor_025 | cued_slow |
|---|---|---|---|---|---|---|---|
| all | 383 | 79.4% / 85.2% | 83.8% / 89.3% | 77.0% / 83.8% | 81.2% / 87.4% | 80.2% / 85.9% | 79.9% / 85.6% |
| one evidence | 291 | 91.4% / 91.4% | 94.2% / 94.2% | 87.6% / 87.6% | 91.8% / 91.8% | 91.4% / 91.4% | 91.1% / 91.1% |
| several | 92 | 41.3% / 65.7% | 51.1% / 74.1% | 43.5% / 71.5% | 47.8% / 73.7% | 44.6% / 68.4% | 44.6% / 68.4% |
| oldest under 30 d | 73 | 98.6% / 99.3% | 93.2% / 95.2% | 86.3% / 88.4% | 95.9% / 97.3% | 97.3% / 98.6% | 97.3% / 98.6% |
| oldest 30-90 d | 98 | 82.7% / 86.2% | 88.8% / 91.5% | 77.6% / 81.1% | 82.7% / 85.7% | 83.7% / 86.7% | 82.7% / 85.7% |
| oldest 90-180 d | 164 | 76.8% / 83.8% | 81.1% / 87.6% | 76.8% / 84.5% | 78.7% / 86.0% | 77.4% / 84.4% | 77.4% / 84.4% |
| oldest over 180 d | 48 | 52.1% / 66.8% | 68.8% / 81.9% | 62.5% / 79.6% | 64.6% / 80.7% | 56.2% / 69.9% | 56.2% / 69.9% |

+1d: paired against auto (questions with all evidence only under the arm / only under auto), and the same split by oldest-evidence bucket

| arm | gained | lost | net | under 30 d | 30-90 d | 90-180 d | over 180 d |
|---|---|---|---|---|---|---|---|
| flat | 22 | 5 | +17 | +0/-4 | +6/-0 | +8/-1 | +8/-0 |
| cued_direct | 16 | 25 | -9 | +0/-9 | +3/-8 | +6/-6 | +7/-2 |
| cued_floor_040 | 15 | 8 | +7 | +0/-2 | +3/-3 | +5/-2 | +7/-1 |
| cued_floor_025 | 7 | 4 | +3 | +0/-1 | +3/-2 | +2/-1 | +2/-0 |
| cued_slow | 8 | 6 | +2 | +0/-1 | +3/-3 | +3/-2 | +2/-0 |

+1d: evidence turns shown, by the turn's own age (turn-question pairs)

| turn age | pairs | auto | flat | cued_direct | cued_floor_040 | cued_floor_025 | cued_slow |
|---|---|---|---|---|---|---|---|
| under 30 d | 97 | 95.9% | 89.7% | 85.6% | 92.8% | 94.8% | 94.8% |
| 30-90 d | 138 | 83.3% | 87.7% | 78.3% | 82.6% | 83.3% | 82.6% |
| 90-180 d | 222 | 74.8% | 82.4% | 79.3% | 80.2% | 77.5% | 77.5% |
| over 180 d | 62 | 59.7% | 75.8% | 77.4% | 77.4% | 61.3% | 61.3% |

+1d: evidence turns shown, cued vs uncued turns (turn-question pairs)

| evidence turn | pairs | auto | flat | cued_direct | cued_floor_040 | cued_floor_025 | cued_slow |
|---|---|---|---|---|---|---|---|
| cued | 450 | 82.9% | 88.0% | 88.4% | 88.2% | 85.1% | 85.1% |
| cued, under 30 d | 82 | 96.3% | 92.7% | 93.9% | 93.9% | 95.1% | 95.1% |
| cued, 30-90 d | 115 | 89.6% | 92.2% | 92.2% | 92.2% | 92.2% | 92.2% |
| cued, 90-180 d | 198 | 78.8% | 86.4% | 84.8% | 84.8% | 82.3% | 82.3% |
| cued, over 180 d | 55 | 63.6% | 78.2% | 85.5% | 83.6% | 65.5% | 65.5% |
| uncued | 69 | 55.1% | 60.9% | 24.6% | 47.8% | 49.3% | 47.8% |
| uncued, under 30 d | 15 | 93.3% | 73.3% | 40.0% | 86.7% | 93.3% | 93.3% |
| uncued, 30-90 d | 23 | 52.2% | 65.2% | 8.7% | 34.8% | 39.1% | 34.8% |
| uncued, 90-180 d | 24 | 41.7% | 50.0% | 33.3% | 41.7% | 37.5% | 37.5% |
| uncued, over 180 d | 7 | 28.6% | 57.1% | 14.3% | 28.6% | 28.6% | 28.6% |

### +365d: all evidence shown % / mean evidence share % (n questions)

| group | n | auto | flat | cued_direct | cued_floor_040 | cued_floor_025 | cued_slow |
|---|---|---|---|---|---|---|---|
| all | 383 | 83.8% / 89.3% | 83.8% / 89.3% | 76.2% / 82.8% | 78.9% / 85.4% | 80.7% / 86.9% | 82.5% / 88.6% |
| one evidence | 291 | 94.2% / 94.2% | 94.2% / 94.2% | 86.6% / 86.6% | 89.7% / 89.7% | 91.1% / 91.1% | 93.5% / 93.5% |
| several | 92 | 51.1% / 74.1% | 51.1% / 74.1% | 43.5% / 70.9% | 44.6% / 72.0% | 47.8% / 73.8% | 47.8% / 73.0% |
| oldest 365-395 d | 78 | 92.3% / 95.1% | 92.3% / 95.1% | 82.1% / 84.8% | 85.9% / 88.7% | 88.5% / 91.2% | 91.0% / 93.8% |
| oldest 395-455 d | 95 | 89.5% / 91.6% | 89.5% / 91.6% | 77.9% / 80.8% | 81.1% / 84.0% | 82.1% / 85.1% | 88.4% / 91.4% |
| oldest 455-545 d | 162 | 80.9% / 87.4% | 80.9% / 87.4% | 76.5% / 84.0% | 78.4% / 85.9% | 80.2% / 87.6% | 79.6% / 86.8% |
| oldest over 545 d | 48 | 68.8% / 81.9% | 68.8% / 81.9% | 62.5% / 79.6% | 64.6% / 81.7% | 66.7% / 81.4% | 66.7% / 80.3% |

+365d: paired against auto (questions with all evidence only under the arm / only under auto), and the same split by oldest-evidence bucket

| arm | gained | lost | net | 365-395 d | 395-455 d | 455-545 d | over 545 d |
|---|---|---|---|---|---|---|---|
| flat | 0 | 0 | +0 | +0/-0 | +0/-0 | +0/-0 | +0/-0 |
| cued_direct | 3 | 32 | -29 | +0/-8 | +1/-12 | +2/-9 | +0/-3 |
| cued_floor_040 | 3 | 22 | -19 | +0/-5 | +1/-9 | +2/-6 | +0/-2 |
| cued_floor_025 | 3 | 15 | -12 | +0/-3 | +1/-8 | +2/-3 | +0/-1 |
| cued_slow | 1 | 6 | -5 | +0/-1 | +0/-1 | +1/-3 | +0/-1 |

+365d: evidence turns shown, by the turn's own age (turn-question pairs)

| turn age | pairs | auto | flat | cued_direct | cued_floor_040 | cued_floor_025 | cued_slow |
|---|---|---|---|---|---|---|---|
| 365-395 d | 104 | 90.4% | 90.4% | 82.7% | 86.5% | 88.5% | 90.4% |
| 395-455 d | 134 | 87.3% | 87.3% | 77.6% | 79.9% | 81.3% | 86.6% |
| 455-545 d | 219 | 82.2% | 82.2% | 79.0% | 80.4% | 82.2% | 80.8% |
| over 545 d | 62 | 75.8% | 75.8% | 77.4% | 79.0% | 79.0% | 74.2% |

+365d: evidence turns shown, cued vs uncued turns (turn-question pairs)

| evidence turn | pairs | auto | flat | cued_direct | cued_floor_040 | cued_floor_025 | cued_slow |
|---|---|---|---|---|---|---|---|
| cued | 450 | 88.0% | 88.0% | 88.4% | 88.7% | 89.1% | 87.6% |
| cued, 365-395 d | 89 | 93.3% | 93.3% | 94.4% | 94.4% | 94.4% | 94.4% |
| cued, 395-455 d | 111 | 91.9% | 91.9% | 91.9% | 91.9% | 91.9% | 91.9% |
| cued, 455-545 d | 195 | 86.2% | 86.2% | 84.6% | 85.1% | 86.7% | 85.1% |
| cued, over 545 d | 55 | 78.2% | 78.2% | 85.5% | 85.5% | 83.6% | 76.4% |
| uncued | 69 | 60.9% | 60.9% | 18.8% | 33.3% | 42.0% | 56.5% |
| uncued, 365-395 d | 15 | 73.3% | 73.3% | 13.3% | 40.0% | 53.3% | 66.7% |
| uncued, 395-455 d | 23 | 65.2% | 65.2% | 8.7% | 21.7% | 30.4% | 60.9% |
| uncued, 455-545 d | 24 | 50.0% | 50.0% | 33.3% | 41.7% | 45.8% | 45.8% |
| uncued, over 545 d | 7 | 57.1% | 57.1% | 14.3% | 28.6% | 42.9% | 57.1% |

## Candidates at +1 d under auto (before the cut to the candidate limit)

- questions 383, candidates per question 297.0; any direct-weighted candidate: 0
- share of candidates that are cued: mean per question 44.8% (median 43.8%); pooled 50582/113752 = 44.5%
- mean age, cued candidates: 88.6 d (mean of per-question means), pooled 88.9 d
- mean age, uncued candidates: 88.8 d (mean of per-question means), pooled 88.9 d
- evidence statements among candidates: 1185, of which cued 1088 (91.8%)
- evidence turns shown under auto at +1 d: 411; cued 373, uncued 38

## Against the original brains without cues (2026-11-12 run)

- +1d auto: without cues 77.5% / 83.5%, with cues 79.4% / 85.2% (+1.8%); questions gained 17, lost 10; evidence sets differ in 41
- +1d flat: without cues 80.4% / 85.7%, with cues 83.8% / 89.3% (+3.4%); questions gained 19, lost 6; evidence sets differ in 41
- +365d auto: without cues 80.4% / 85.7%, with cues 83.8% / 89.3% (+3.4%); questions gained 19, lost 6; evidence sets differ in 41
- +365d flat: without cues 80.4% / 85.7%, with cues 83.8% / 89.3% (+3.4%); questions gained 19, lost 6; evidence sets differ in 41

- +1d flat equals +365d flat question for question: 383 of 383
