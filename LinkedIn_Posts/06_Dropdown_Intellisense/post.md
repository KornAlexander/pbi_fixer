# LinkedIn Post — Dropdown Selection with Intellisense

**Image:** report-explorer.png (showing the dropdown/combobox area)

---

Small thing. Big difference.

When you launch the PBI Fixer, you need to select which report or semantic model to work with. In a workspace with 50+ items, typing the exact name from memory is painful.

So we added intellisense-style autocomplete:

1. Click "List Items" → fetches all reports and models from your workspace
2. Start typing → dropdown filters in real-time
3. Icons distinguish types: 📊 report-only, 📄 model-only, bare name = both
4. Comma-separated multi-select with per-segment autocomplete
5. Already selected items are filtered out of the suggestions

Type `"Sales"` → see `"Sales Dashboard"`, `"Sales Model"`, `"Sales QA Report"`.

Select one, type a comma, start typing the next → only remaining items shown.

It's the kind of UX detail that makes the difference between "I'll use this tool" and "I'll just type it manually."

Try it: https://actionablereporting.com/pbi-fixer

#PowerBI #MicrosoftFabric #UX #DataAnalytics #SemanticLinkLabs #OpenSource
