# Data notes

## Kaggle files

Fetched with `python -m swf kaggle` (kaggle CLI; token supplied via the CLI's own env/config, not by swf).

| File | Rows | Expected |
|---|---|---|
| Plant_1_Generation_Data.csv | 68778 | 68778 |
| Plant_1_Weather_Sensor_Data.csv | 3182 | 3182 |
| Plant_2_Generation_Data.csv | 67698 | 67698 |
| Plant_2_Weather_Sensor_Data.csv | 3259 | 3259 |
| T1.csv | 50530 | 50530 |

Phase 3 parsing notes:
- T1.csv starts with a UTF-8 BOM: read with `encoding="utf-8-sig"`.
- Plant 1 generation dates are `dd-mm-yyyy HH:MM`; the other solar files are ISO.
