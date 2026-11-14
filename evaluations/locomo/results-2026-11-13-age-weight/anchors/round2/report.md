- conv-26: floor 0.3; anchored events {'matched_turn': 42, 'matched_session': 28, 'real_turn': 44, 'real_session': 108} (anchor turns {'matched_turn': 42, 'matched_session': 28, 'real_turn': 44, 'real_session': 108}); top lifts +1d {'lists': 600, 'lifted': 23326, 'max_factor': 1.8285020831244163}, +365d {'lists': 600, 'lifted': 23326, 'max_factor': 1.0001025237998429}
- conv-30: floor 0.3; anchored events {'matched_turn': 32, 'matched_session': 18, 'real_turn': 35, 'real_session': 87} (anchor turns {'matched_turn': 32, 'matched_session': 18, 'real_turn': 35, 'real_session': 87}); top lifts +1d {'lists': 324, 'lifted': 12875, 'max_factor': 1.8371613904185897}, +365d {'lists': 324, 'lifted': 12875, 'max_factor': 1.0001031071257416}
- conv-41: floor 0.3; anchored events {'matched_turn': 77, 'matched_session': 35, 'real_turn': 84, 'real_session': 168} (anchor turns {'matched_turn': 77, 'matched_session': 35, 'real_turn': 84, 'real_session': 168}); top lifts +1d {'lists': 608, 'lifted': 31437, 'max_factor': 1.849655641864753}, +365d {'lists': 608, 'lifted': 31437, 'max_factor': 1.0001039391654032}

## +1d (n = 383): all evidence shown % / mean evidence share %

| group | n | auto | flat | real_turn_top | real_session_top | matched_turn_top | matched_session_top | real_turn_fresh | real_session_fresh |
|---|---|---|---|---|---|---|---|---|---|
| all | 383 | 81.5% / 87.1% | 83.8% / 89.3% | 82.8% / 88.7% | 82.5% / 88.4% | 83.8% / 89.3% | 81.2% / 87.4% | 82.8% / 88.7% | 82.5% / 88.4% |
| one evidence | 291 | 93.1% / 93.1% | 94.2% / 94.2% | 93.8% / 93.8% | 93.1% / 93.1% | 94.2% / 94.2% | 92.1% / 92.1% | 93.8% / 93.8% | 93.1% / 93.1% |
| several | 92 | 44.6% / 68.0% | 51.1% / 74.1% | 47.8% / 72.4% | 48.9% / 73.5% | 51.1% / 73.8% | 46.7% / 72.4% | 47.8% / 72.4% | 48.9% / 73.5% |
| oldest under 30 d | 73 | 97.3% / 98.6% | 93.2% / 95.2% | 97.3% / 98.6% | 94.5% / 95.9% | 97.3% / 98.6% | 97.3% / 98.6% | 97.3% / 98.6% | 94.5% / 95.9% |
| oldest 30-90 d | 98 | 84.7% / 88.2% | 88.8% / 91.5% | 84.7% / 88.7% | 85.7% / 88.4% | 85.7% / 89.8% | 83.7% / 86.7% | 84.7% / 88.7% | 85.7% / 88.4% |
| oldest 90-180 d | 164 | 79.3% / 85.7% | 81.1% / 87.6% | 81.1% / 87.6% | 80.5% / 87.4% | 81.7% / 87.9% | 78.7% / 86.3% | 81.1% / 87.6% | 80.5% / 87.4% |
| oldest over 180 d | 48 | 58.3% / 72.0% | 68.8% / 81.9% | 62.5% / 77.2% | 64.6% / 80.3% | 66.7% / 78.8% | 60.4% / 75.1% | 62.5% / 77.2% | 64.6% / 80.3% |

+1d: paired against auto (gained / lost), overall and in the under 30 d bucket; identical evidence sets

| arm | all | net | under 30 d | identical sets |
|---|---|---|---|---|
| flat | +13/-4 | +9 | +0/-3 | 358/383 |
| real_turn_top | +9/-4 | +5 | +0/-0 | 363/383 |
| real_session_top | +14/-10 | +4 | +0/-2 | 350/383 |
| matched_turn_top | +12/-3 | +9 | +0/-0 | 362/383 |
| matched_session_top | +3/-4 | -1 | +0/-0 | 370/383 |
| real_turn_fresh | +9/-4 | +5 | +0/-0 | 363/383 |
| real_session_fresh | +14/-10 | +4 | +0/-2 | 350/383 |

+1d: evidence turns shown, real_turn anchors: anchored vs not anchored, by the turn's age

| evidence turns | pairs | auto | flat | real_turn_top | real_turn_fresh |
|---|---|---|---|---|---|
| anchored, all ages | 226 | 85.8% | 88.1% | 92.5% | 92.5% |
| anchored, under 30 d | 46 | 91.3% | 89.1% | 89.1% | 89.1% |
| anchored, 30-90 d | 65 | 89.2% | 92.3% | 95.4% | 95.4% |
| anchored, 90-180 d | 95 | 86.3% | 90.5% | 93.7% | 93.7% |
| anchored, over 180 d | 20 | 60.0% | 60.0% | 85.0% | 85.0% |
| anchored, older than 90 d | 115 | 81.7% | 85.2% | 92.2% | 92.2% |
| not anchored, all ages | 293 | 77.5% | 81.6% | 76.5% | 76.5% |
| not anchored, under 30 d | 51 | 98.0% | 90.2% | 98.0% | 98.0% |
| not anchored, 30-90 d | 73 | 80.8% | 83.6% | 75.3% | 75.3% |
| not anchored, 90-180 d | 127 | 71.7% | 76.4% | 71.7% | 71.7% |
| not anchored, over 180 d | 42 | 64.3% | 83.3% | 66.7% | 66.7% |
| not anchored, older than 90 d | 169 | 69.8% | 78.1% | 70.4% | 70.4% |

+1d: evidence turns shown, real_session anchors: anchored vs not anchored, by the turn's age

| evidence turns | pairs | auto | flat | real_session_top | real_session_fresh |
|---|---|---|---|---|---|
| anchored, all ages | 322 | 81.7% | 85.1% | 88.8% | 88.8% |
| anchored, under 30 d | 57 | 93.0% | 89.5% | 91.2% | 91.2% |
| anchored, 30-90 d | 76 | 85.5% | 89.5% | 88.2% | 88.2% |
| anchored, 90-180 d | 138 | 81.9% | 85.5% | 90.6% | 90.6% |
| anchored, over 180 d | 51 | 62.7% | 72.5% | 82.4% | 82.4% |
| anchored, older than 90 d | 189 | 76.7% | 82.0% | 88.4% | 88.4% |
| not anchored, all ages | 197 | 80.2% | 83.2% | 75.1% | 75.1% |
| not anchored, under 30 d | 40 | 97.5% | 90.0% | 92.5% | 92.5% |
| not anchored, 30-90 d | 62 | 83.9% | 85.5% | 79.0% | 79.0% |
| not anchored, 90-180 d | 84 | 71.4% | 77.4% | 65.5% | 65.5% |
| not anchored, over 180 d | 11 | 63.6% | 90.9% | 63.6% | 63.6% |
| not anchored, older than 90 d | 95 | 70.5% | 78.9% | 65.3% | 65.3% |

+1d: evidence turns shown, matched_turn anchors: anchored vs not anchored, by the turn's age

| evidence turns | pairs | auto | flat | matched_turn_top |
|---|---|---|---|---|
| anchored, all ages | 191 | 84.8% | 87.4% | 94.2% |
| anchored, under 30 d | 40 | 92.5% | 90.0% | 92.5% |
| anchored, 30-90 d | 53 | 90.6% | 94.3% | 98.1% |
| anchored, 90-180 d | 79 | 83.5% | 88.6% | 93.7% |
| anchored, over 180 d | 19 | 57.9% | 57.9% | 89.5% |
| anchored, older than 90 d | 98 | 78.6% | 82.7% | 92.9% |
| not anchored, all ages | 328 | 79.0% | 82.6% | 78.4% |
| not anchored, under 30 d | 57 | 96.5% | 89.5% | 96.5% |
| not anchored, 30-90 d | 85 | 81.2% | 83.5% | 77.6% |
| not anchored, 90-180 d | 143 | 74.8% | 79.0% | 74.8% |
| not anchored, over 180 d | 43 | 65.1% | 83.7% | 67.4% |
| not anchored, older than 90 d | 186 | 72.6% | 80.1% | 73.1% |

+1d: evidence turns shown, matched_session anchors: anchored vs not anchored, by the turn's age

| evidence turns | pairs | auto | flat | matched_session_top |
|---|---|---|---|---|
| anchored, all ages | 84 | 82.1% | 85.7% | 92.9% |
| anchored, under 30 d | 24 | 87.5% | 83.3% | 87.5% |
| anchored, 30-90 d | 15 | 93.3% | 93.3% | 100.0% |
| anchored, 90-180 d | 32 | 78.1% | 87.5% | 90.6% |
| anchored, over 180 d | 13 | 69.2% | 76.9% | 100.0% |
| anchored, older than 90 d | 45 | 75.6% | 84.4% | 93.3% |
| not anchored, all ages | 435 | 80.9% | 84.1% | 80.2% |
| not anchored, under 30 d | 73 | 97.3% | 91.8% | 97.3% |
| not anchored, 30-90 d | 123 | 83.7% | 87.0% | 82.1% |
| not anchored, 90-180 d | 190 | 77.9% | 81.6% | 77.4% |
| not anchored, over 180 d | 49 | 61.2% | 75.5% | 61.2% |
| not anchored, older than 90 d | 239 | 74.5% | 80.3% | 74.1% |

## +365d (n = 383): all evidence shown % / mean evidence share %

| group | n | auto | flat | real_turn_top | real_session_top | matched_turn_top | matched_session_top | real_turn_fresh | real_session_fresh |
|---|---|---|---|---|---|---|---|---|---|
| all | 383 | 83.8% / 89.3% | 83.8% / 89.3% | 83.8% / 89.3% | 83.8% / 89.3% | 83.8% / 89.3% | 83.8% / 89.3% | 82.2% / 88.1% | 82.8% / 88.6% |
| one evidence | 291 | 94.2% / 94.2% | 94.2% / 94.2% | 94.2% / 94.2% | 94.2% / 94.2% | 94.2% / 94.2% | 94.2% / 94.2% | 92.4% / 92.4% | 93.1% / 93.1% |
| several | 92 | 51.1% / 74.1% | 51.1% / 74.1% | 51.1% / 74.1% | 51.1% / 74.1% | 51.1% / 74.1% | 51.1% / 74.1% | 50.0% / 74.6% | 50.0% / 74.3% |
| oldest 365-395 d | 78 | 92.3% / 95.1% | 92.3% / 95.1% | 92.3% / 95.1% | 92.3% / 95.1% | 92.3% / 95.1% | 92.3% / 95.1% | 89.7% / 92.5% | 88.5% / 90.6% |
| oldest 395-455 d | 95 | 89.5% / 91.6% | 89.5% / 91.6% | 89.5% / 91.6% | 89.5% / 91.6% | 89.5% / 91.6% | 89.5% / 91.6% | 84.2% / 87.7% | 88.4% / 90.5% |
| oldest 455-545 d | 162 | 80.9% / 87.4% | 80.9% / 87.4% | 80.9% / 87.4% | 80.9% / 87.4% | 80.9% / 87.4% | 80.9% / 87.4% | 82.1% / 88.3% | 82.1% / 88.8% |
| oldest over 545 d | 48 | 68.8% / 81.9% | 68.8% / 81.9% | 68.8% / 81.9% | 68.8% / 81.9% | 68.8% / 81.9% | 68.8% / 81.9% | 66.7% / 81.4% | 64.6% / 80.8% |

+365d: paired against auto (gained / lost), overall and in the 365-395 d bucket; identical evidence sets

| arm | all | net | 365-395 d | identical sets |
|---|---|---|---|---|
| flat | +0/-0 | +0 | +0/-0 | 383/383 |
| real_turn_top | +0/-0 | +0 | +0/-0 | 383/383 |
| real_session_top | +0/-0 | +0 | +0/-0 | 383/383 |
| matched_turn_top | +0/-0 | +0 | +0/-0 | 383/383 |
| matched_session_top | +0/-0 | +0 | +0/-0 | 383/383 |
| real_turn_fresh | +7/-13 | -6 | +0/-2 | 354/383 |
| real_session_fresh | +11/-15 | -4 | +1/-4 | 347/383 |

+365d: evidence turns shown, real_turn anchors: anchored vs not anchored, by the turn's age

| evidence turns | pairs | auto | flat | real_turn_top | real_turn_fresh |
|---|---|---|---|---|---|
| anchored, all ages | 226 | 88.1% | 88.1% | 88.1% | 94.2% |
| anchored, 365-395 d | 51 | 90.2% | 90.2% | 90.2% | 92.2% |
| anchored, 395-455 d | 60 | 91.7% | 91.7% | 91.7% | 95.0% |
| anchored, 455-545 d | 95 | 90.5% | 90.5% | 90.5% | 95.8% |
| anchored, over 545 d | 20 | 60.0% | 60.0% | 60.0% | 90.0% |
| not anchored, all ages | 293 | 81.6% | 81.6% | 81.6% | 75.8% |
| not anchored, 365-395 d | 53 | 90.6% | 90.6% | 90.6% | 86.8% |
| not anchored, 395-455 d | 74 | 83.8% | 83.8% | 83.8% | 73.0% |
| not anchored, 455-545 d | 124 | 75.8% | 75.8% | 75.8% | 74.2% |
| not anchored, over 545 d | 42 | 83.3% | 83.3% | 83.3% | 71.4% |

+365d: evidence turns shown, real_session anchors: anchored vs not anchored, by the turn's age

| evidence turns | pairs | auto | flat | real_session_top | real_session_fresh |
|---|---|---|---|---|---|
| anchored, all ages | 322 | 85.1% | 85.1% | 85.1% | 90.4% |
| anchored, 365-395 d | 62 | 90.3% | 90.3% | 90.3% | 93.5% |
| anchored, 395-455 d | 71 | 88.7% | 88.7% | 88.7% | 90.1% |
| anchored, 455-545 d | 138 | 85.5% | 85.5% | 85.5% | 91.3% |
| anchored, over 545 d | 51 | 72.5% | 72.5% | 72.5% | 84.3% |
| not anchored, all ages | 197 | 83.2% | 83.2% | 83.2% | 73.6% |
| not anchored, 365-395 d | 42 | 90.5% | 90.5% | 90.5% | 81.0% |
| not anchored, 395-455 d | 63 | 85.7% | 85.7% | 85.7% | 77.8% |
| not anchored, 455-545 d | 81 | 76.5% | 76.5% | 76.5% | 67.9% |
| not anchored, over 545 d | 11 | 90.9% | 90.9% | 90.9% | 63.6% |

+365d: evidence turns shown, matched_turn anchors: anchored vs not anchored, by the turn's age

| evidence turns | pairs | auto | flat | matched_turn_top |
|---|---|---|---|---|
| anchored, all ages | 191 | 87.4% | 87.4% | 87.4% |
| anchored, 365-395 d | 45 | 91.1% | 91.1% | 91.1% |
| anchored, 395-455 d | 48 | 93.8% | 93.8% | 93.8% |
| anchored, 455-545 d | 79 | 88.6% | 88.6% | 88.6% |
| anchored, over 545 d | 19 | 57.9% | 57.9% | 57.9% |
| not anchored, all ages | 328 | 82.6% | 82.6% | 82.6% |
| not anchored, 365-395 d | 59 | 89.8% | 89.8% | 89.8% |
| not anchored, 395-455 d | 86 | 83.7% | 83.7% | 83.7% |
| not anchored, 455-545 d | 140 | 78.6% | 78.6% | 78.6% |
| not anchored, over 545 d | 43 | 83.7% | 83.7% | 83.7% |

+365d: evidence turns shown, matched_session anchors: anchored vs not anchored, by the turn's age

| evidence turns | pairs | auto | flat | matched_session_top |
|---|---|---|---|---|
| anchored, all ages | 84 | 85.7% | 85.7% | 85.7% |
| anchored, 365-395 d | 25 | 84.0% | 84.0% | 84.0% |
| anchored, 395-455 d | 14 | 92.9% | 92.9% | 92.9% |
| anchored, 455-545 d | 32 | 87.5% | 87.5% | 87.5% |
| anchored, over 545 d | 13 | 76.9% | 76.9% | 76.9% |
| not anchored, all ages | 435 | 84.1% | 84.1% | 84.1% |
| not anchored, 365-395 d | 79 | 92.4% | 92.4% | 92.4% |
| not anchored, 395-455 d | 120 | 86.7% | 86.7% | 86.7% |
| not anchored, 455-545 d | 187 | 81.3% | 81.3% | 81.3% |
| not anchored, over 545 d | 49 | 75.5% | 75.5% | 75.5% |

## Candidates at +1 d under auto

- 383 questions, 297.0 candidates per question, mean age 88.6 d, mean of the per-question highest weight 0.556
- real_turn: share of candidates anchored, mean per question 13.1% (pooled 15006/113752); mean age of anchored candidates 93.7 d
- real_session: share of candidates anchored, mean per question 28.1% (pooled 31778/113752); mean age of anchored candidates 101.6 d
- matched_turn: share of candidates anchored, mean per question 11.8% (pooled 13552/113752); mean age of anchored candidates 92.7 d
- matched_session: share of candidates anchored, mean per question 6.5% (pooled 7311/113752); mean age of anchored candidates 85.0 d

## Rule (fixed in advance)

- real_turn_top: +1d recent lost 0, +365d net +0 -> ACCEPTABLE; +1d net +5; anchored >90 d shown +10.4%, not anchored >90 d +0.6% (all ages -1.0%) -> WORTH BUILDING
- real_session_top: +1d recent lost 2, +365d net +0 -> not acceptable; +1d net +4; anchored >90 d shown +11.6%, not anchored >90 d -5.3% (all ages -5.1%) -> not worth building
- matched_turn_top: +1d recent lost 0, +365d net +0 -> ACCEPTABLE; +1d net +9; anchored >90 d shown +14.3%, not anchored >90 d +0.5% (all ages -0.6%) -> WORTH BUILDING
- matched_session_top: +1d recent lost 0, +365d net +0 -> ACCEPTABLE; +1d net -1; anchored >90 d shown +17.8%, not anchored >90 d -0.4% (all ages -0.7%) -> WORTH BUILDING
- real_turn_fresh: +1d recent lost 0, +365d net -6 -> not acceptable; +1d net +5; anchored >90 d shown +10.4%, not anchored >90 d +0.6% (all ages -1.0%) -> not worth building
- real_session_fresh: +1d recent lost 2, +365d net -4 -> not acceptable; +1d net +4; anchored >90 d shown +11.6%, not anchored >90 d -5.3% (all ages -5.1%) -> not worth building

## +365 d: top arms against auto, question by question

- real_turn_top differs from auto in 0 of 383: []
- real_session_top differs from auto in 0 of 383: []
- matched_turn_top differs from auto in 0 of 383: []
- matched_session_top differs from auto in 0 of 383: []
- auto identical to round 1 in 766 of 766 question-times
- flat identical to round 1 in 766 of 766 question-times
