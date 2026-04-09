# LinkedIn Post — Direct Lake Cache Pre-Warm

**Image:** model-explorer.png (or screenshot of cache warming action in SM Explorer)

---

"Why is my Direct Lake report slow in the morning?"

Because the cache is cold. Every. Single. Morning.

Direct Lake is blazing fast — when the data is resident in memory. But after nightly refreshes or idle periods, your columns get evicted. First user of the day gets the penalty.

The PBI Fixer now automates this entirely:

1. Scans your Direct Lake model for currently resident columns
2. Creates a `_CacheWarmUp` perspective with those columns (+ relationship key dependencies)
3. Generates a warm-up notebook
4. Schedules it daily at 07:00 via the Fabric Job Scheduler API

One click. No more cold mornings.

It even has a scan-only mode — so you can preview what would happen before committing.

This runs natively in Microsoft Fabric Notebooks. No external tools needed.

Try it: https://actionablereporting.com/pbi-fixer

#PowerBI #MicrosoftFabric #DirectLake #DataAnalytics #SemanticLinkLabs #OpenSource
