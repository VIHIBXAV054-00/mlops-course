# Week 4 batches

The Week 4 lab (DVC) uses three batches, so that the dataset gets three versions. They
are the two shared batches in `datasets/batches/`, with the second one split by date. No
row and no value is changed, and the order of the rows is kept.

| File | Rows | Dates (synthetic) | Source |
| :--- | :--- | :--- | :--- |
| `batch_01.csv` | 461 | 2024-01-01 → 2024-03-30 | all of `batch_01_baseline.csv` |
| `batch_02.csv` | 107 | 2024-03-31 → 2024-04-30 | `batch_02_new_arrival.csv`, rows up to April |
| `batch_03.csv` | 200 | 2024-05-01 → 2024-06-28 | `batch_02_new_arrival.csv`, rows from May |

Merged in this order, the three batches give the same bytes as the two shared batches
merged, so the full dataset in Week 4 has the same md5 as in Weeks 5–13.

`scripts/sync_datasets.sh` copies these files into `data/incoming/` of both Week 4 lab
folders. Other weeks use the shared batches.

To regenerate them, split `batch_02_new_arrival.csv` after its last April row: keep the
header line in both parts, and copy the lines unchanged.
