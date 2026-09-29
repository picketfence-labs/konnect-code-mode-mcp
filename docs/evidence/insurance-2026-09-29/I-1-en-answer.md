Based on the data retrieved from the Insurance APIs, here are the insurance products ranked by their policy conversion rate (issued policies divided by applications):

| Rank | Product ID | Product Name | Applications | Issued Policies | Conversion Rate |
| :--- | :--- | :--- | :---: | :---: | :---: |
| 1 | `PRD-002` | 自動車保険「ドライブセーフ」 (Auto Insurance) | 54 | 40 | **74.07%** |
| 2 | `PRD-003` | 傷害保険「ケガの安心サポート」 (Personal Accident Insurance) | 59 | 41 | **69.49%** |
| 3 | `PRD-005` | ペット保険「わんにゃんメディカル」 (Pet Insurance) | 68 | 46 | **67.65%** |
| 4 | `PRD-001` | 火災保険「住まいの安心」 (Fire Insurance) | 71 | 45 | **63.38%** |
| 5 | `PRD-004` | 医療保険「メディカルサポート」 (Medical Insurance) | 48 | 28 | **58.33%** |

### Summary of Methodology:
1. **Products Retrieval:** Obtained all property insurance products to map IDs to their names.
2. **Applications Counting:** Fetched all 300 active/pending application records using paginated requests to ensure full coverage.
3. **Policies Counting:** Fetched all 200 issued policy records similarly.
4. **Aggregation:** Grouped the applications and policies by `product_id`, calculated the conversion rate for each, and sorted the results in descending order.