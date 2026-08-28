# Keeper files

One JSON file per keeper league (RFN, Dirty Boys — Kings has no keepers).
Fill in before the draft:

```json
[
  {"player": "Ashton Jeanty", "cost_round": 7},
  {"player": "Bijan Robinson", "cost_round": 3}
]
```

`cost_round` is the round it costs to keep them this year (one round
earlier than the round they were drafted in last year, per league rules).
Player name should match the spelling in `RankingsTiersMarketScore_2026.xlsx`
(the crosswalk's name normalization handles case/punctuation differences,
but not nicknames it hasn't seen before — check `backend/crosswalk.py`'s
`NAME_ALIASES` if a keeper doesn't get picked up).
