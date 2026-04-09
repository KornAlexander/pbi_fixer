# LinkedIn Post — Incremental Refresh Setup (One Click vs. Desktop Pain)

**Image:** model-explorer.png (or screenshot of incremental refresh in action)

---

Setting up incremental refresh in Power BI Desktop is a 6-step obstacle course:

1. Create a `RangeStart` parameter (DateTime, exact name, exact casing)
2. Create a `RangeEnd` parameter (same rules)
3. Open Power Query, find the right table, add a filter step referencing both parameters
4. Close Power Query, right-click the table → "Incremental refresh and real-time data"
5. Configure the policy: how many years for the rolling window, how many days for the incremental window, complete days only?
6. Publish to the service

Miss any step? Wrong parameter name? Forgot the filter step? Policy won't apply. And the error messages won't tell you why.

The PBI Fixer does all of this. Automatically:

✅ Auto-detects the DateTime column in each table
✅ Creates `RangeStart` and `RangeEnd` as M parameters (exact names, exact types)
✅ Modifies the Power Query expression — adds the filter step referencing both parameters
✅ Sets the refresh policy: rolling window (years), incremental window (days), complete-days offset
✅ Applies via XMLA — no publish step needed. It's live immediately.

And it does this for every qualifying table in the model. In one pass.

Tables that already have a policy? Skipped.
Calculated tables? Skipped.
Tables without a DateTime column? Skipped.

No Desktop. No manual parameter creation. No forgotten filter steps. No broken policies.

One click.

Try it: https://actionablereporting.com/pbi-fixer

#PowerBI #MicrosoftFabric #IncrementalRefresh #DataEngineering #SemanticLinkLabs #OpenSource
