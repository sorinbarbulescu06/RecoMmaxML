# Stage 1 baseline (before any fix)

| log | queries | API calls | API ok | API errors | fallbacks | queries with 0 active conditions |
|---|---|---|---|---|---|---|
| noLocalJustAPI.txt | 12 | 12 (100%) | 11 | 1 {'503': 1} | 0 | 1 |
| LocalAndAPI.txt | 12 | 12 (100%) | 11 | 1 {'503': 1} | 0 | 0 |
| LocalNoAPI.txt | 12 | 0 (0%) | 0 | 0 {} | 0 | 0 |
| out_first100query.txt | 100 | 0 (0%) | 0 | 0 {} | 0 | 0 |
