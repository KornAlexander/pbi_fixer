# LinkedIn Post — Refresh Tables & Partitions with Mode Selection

**Image:** model-explorer.png (showing the refresh dropdown at the bottom of SM Explorer)

---

Power BI refresh is all or nothing. Right?

Wrong.

Sometimes you need to refresh just one table. Or one partition. Or you just need a recalculation — no data reload.

The PBI Fixer gives you granular refresh control directly in the Semantic Model Explorer:

- Select a **table** in the tree → "🔄 Refresh Table"
- Drill into **partitions** → "🔄 Refresh Partition"
- Pick your **refresh mode** from the dropdown:
  - `automatic` — let the engine decide
  - `dataOnly` — reload data, skip recalculation
  - `full` — complete reload + recalculate
  - `calculate` — recalculate only, no data reload

Why does this matter?

Scenario: You fixed a DAX measure. You don't need to reload 200M rows. You need `calculate`. Done in seconds instead of minutes.

Scenario: One source table had bad data. Refresh just that table. Not the entire model.

Scenario: You're testing incremental refresh partitions. Refresh one partition to verify — not the whole rolling window.

This runs via the Fabric REST API. No Power BI Desktop needed.

Try it: 🎯 https://actionablereporting.com/pbi-fixer

#PowerBI #MicrosoftFabric #DataEngineering #SemanticLinkLabs #OpenSource
# LinkedIn Post â€” Refresh Tables & Partitions with Mode Selection

**Image:** model-explorer.png (showing the refresh dropdown at the bottom of SM Explorer)

---

Power BI refresh is all or nothing. Right?

Wrong.

Sometimes you need to refresh just one table. Or one partition. Or you just need a recalculation â€” no data reload.

The PBI Fixer gives you granular refresh control directly in the Semantic Model Explorer:

- Select a **table** in the tree â†’ "ðŸ”„ Refresh Table"
- Drill into **partitions** â†’ "ðŸ”„ Refresh Partition"
- Pick your **refresh mode** from the dropdown:
  - `automatic` â€” let the engine decide
  - `dataOnly` â€” reload data, skip recalculation
  - `full` â€” complete reload + recalculate
  - `calculate` â€” recalculate only, no data reload

Why does this matter?

Scenario: You fixed a DAX measure. You don't need to reload 200M rows. You need `calculate`. Done in seconds instead of minutes.

Scenario: One source table had bad data. Refresh just that table. Not the entire model.

Scenario: You're testing incremental refresh partitions. Refresh one partition to verify â€” not the whole rolling window.

This runs via the Fabric REST API. No Power BI Desktop needed.

Try it: 🎯 https://actionablereporting.com/pbi-fixer

#PowerBI #MicrosoftFabric #DataEngineering #SemanticLinkLabs #OpenSource
