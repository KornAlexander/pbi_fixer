# LinkedIn Post — Structure Chart Fix (IBCS Column→Bar)

**Image:** ibcs-implementation.png

---

Quick IBCS rule that most Power BI reports get wrong:

- **Time series** → vertical columns (left to right)
- **Structural comparisons** → horizontal bars (top to bottom)

Products by revenue? Bar chart. Not column chart.
Regions by headcount? Bar chart.
Monthly trend? Column chart.

Simple rule. Almost never followed.

The PBI Fixer detects this automatically:

1. Scans every chart's category axis
2. Checks if the data type is DateTime or matches time patterns (Year, Month, Quarter, Date...)
3. Non-time categories on column charts → converts to bar chart
4. Time categories on bar charts → converts to column chart
5. Preserves stacked/clustered formatting

Additionally, bar charts get sorted descending by the measure — so the longest bar is always at the top. That's IBCS convention for structural comparisons.

It's a small change with a big impact on readability. And it takes exactly zero manual effort.

Try it: https://actionablereporting.com/pbi-fixer

#PowerBI #IBCS #DataVisualization #MicrosoftFabric #SemanticLinkLabs #OpenSource
