# Benchmark Ranking Summary

Baseline: Fixed Chunking 512

## Top 3 by MRR
- **recursive_512**: 0.0150
- **recursive_1024**: 0.0100
- **sentence_512**: 0.0100

## Top 3 by Hit@5
- **sentence_512**: 0.0200
- **recursive_1024**: 0.0200
- **semantic_1024**: 0.0200

## Top 3 by Context Recall
- **sentence_512**: 0.0200
- **recursive_1024**: 0.0200
- **semantic_1024**: 0.0200

## Top 3 by Avg Latency (ms)
- **recursive_512**: 3118.9829
- **parent_child_1024**: 3200.5915
- **recursive_1024**: 3281.2981

## Descriptive Statistics (All Configurations)

|       |    hit_at_5 |         mrr |   context_recall |   context_precision |   avg_latency_ms |   median_latency_ms |
|:------|------------:|------------:|-----------------:|--------------------:|-----------------:|--------------------:|
| count | 15          | 15          |      15          |         15          |            15    |               15    |
| mean  |  0.0146667  |  0.008      |       0.0146667  |          0.00293333 |          4814.53 |             4478.49 |
| std   |  0.00516398 |  0.00316228 |       0.00516398 |          0.0010328  |          1693.86 |             1807.31 |
| min   |  0.01       |  0.005      |       0.01       |          0.002      |          3118.98 |             3163.99 |
| 25%   |  0.01       |  0.005      |       0.01       |          0.002      |          3425.81 |             3244.86 |
| 50%   |  0.01       |  0.01       |       0.01       |          0.002      |          4401.1  |             3279.03 |
| 75%   |  0.02       |  0.01       |       0.02       |          0.004      |          5616.15 |             6792.99 |
| max   |  0.02       |  0.015      |       0.02       |          0.004      |          9201.27 |             7372.91 |
