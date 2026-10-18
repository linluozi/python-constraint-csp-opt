### Upstream vs. optimized (`OptimizedBacktrackingSolver`, default settings)

| case | solutions | constraint calls (upstream) | constraint calls (optimized) | calls ratio | best of 5 (upstream) | best of 5 (optimized) | speed-up |
|---|---:|---:|---:|---:|---:|---:|---:|
| `queens-8-all` | 92 | 24,582 | 21,360 | 1.15x | 0.012 s | 0.010 s | 1.18x |
| `queens-9-all` | 352 | 109,080 | 92,040 | 1.19x | 0.060 s | 0.043 s | 1.42x |
| `queens-10-all` | 724 | 480,304 | 377,782 | 1.27x | 0.219 s | 0.182 s | 1.20x |
| `queens-11-all` | 2,680 | 2,364,060 | 1,769,226 | 1.34x | 2.044 s | 1.814 s | 1.13x |
| `queens-16-first` | 1 | 212,303 | 2,057 | 103.21x | 0.197 s | 0.002 s | 122.87x |
| `queens-20-first` | 1 | 4,902,182 | 6,649 | 737.28x | 4.893 s | 0.005 s | 889.69x |
| `sudoku-hard-all` | 1 | 1,916,096 | 54,594 | 35.10x | 16.882 s | 0.472 s | 35.76x |
| `dedispersion-all` | 11,130 | 17,714 | 17,714 | 1.00x | 0.060 s | 0.061 s | 0.99x |
| `microhh-small-all` | 11,340 | 25,125 | 24,460 | 1.03x | 0.157 s | 0.117 s | 1.34x |
| `hotspot-all` | 349,853 | 914,440 | 853,581 | 1.07x | 2.427 s | 2.399 s | 1.01x |

### Ablation: which optimization is responsible

| case | OptimizedLegacy (s) | OptimizedMRVOnly (s) | OptimizedScopeOnly (s) | OptimizedBacktrackingSolver (s) |
|---|---:|---:|---:|---:|
| `queens-8-all` | 0.012 | 0.024 | 0.021 | 0.011 |
| `queens-9-all` | 0.055 | 0.107 | 0.114 | 0.046 |
| `queens-10-all` | 0.234 | 0.427 | 0.422 | 0.189 |
| `queens-11-all` | 2.611 | 1.878 | 2.713 | 0.898 |
| `queens-16-first` | 0.233 | 0.003 | 0.203 | 0.001 |
| `queens-20-first` | 5.306 | 0.010 | 3.306 | 0.003 |
| `sudoku-hard-all` | 17.331 | 0.674 | 6.108 | 0.219 |
| `dedispersion-all` | 0.081 | 0.074 | 0.027 | 0.031 |
| `microhh-small-all` | 0.185 | 0.164 | 0.053 | 0.059 |
| `hotspot-all` | 3.051 | 3.261 | 1.215 | 1.228 |

### Ablation: constraint invocations

| case | OptimizedLegacy (calls) | OptimizedMRVOnly (calls) | OptimizedScopeOnly (calls) | OptimizedBacktrackingSolver (calls) |
|---|---:|---:|---:|---:|
| `queens-8-all` | 24,582 | 21,360 | 24,582 | 21,360 |
| `queens-9-all` | 109,080 | 92,040 | 109,080 | 92,040 |
| `queens-10-all` | 480,304 | 377,782 | 480,304 | 377,782 |
| `queens-11-all` | 2,364,060 | 1,769,226 | 2,364,060 | 1,769,226 |
| `queens-16-first` | 212,303 | 2,057 | 212,303 | 2,057 |
| `queens-20-first` | 4,902,182 | 6,649 | 4,902,182 | 6,649 |
| `sudoku-hard-all` | 1,916,096 | 54,594 | 1,916,096 | 54,594 |
| `dedispersion-all` | 17,714 | 17,714 | 17,714 | 17,714 |
| `microhh-small-all` | 25,125 | 24,460 | 25,125 | 24,460 |
| `hotspot-all` | 914,440 | 853,581 | 914,440 | 853,581 |
