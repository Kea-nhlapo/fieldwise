# Simulated 7-day reach

**Everything on this page is simulated.** It shows how three ways of choosing Felix's visits perform on the same made-up seasons. It is not field data, and it makes no claim about crop losses avoided.

## The question

Of the farms that develop a real pest or disease problem, what share does Felix visit within 7 days of the problem starting? This is "7-day reach". It measures speed and coverage only.

## Set-up, fixed before the first comparison run

These were committed to git before any comparison was run. The commit history shows the order.

- **Place:** 100 farms in villages of 10, laid out around Bomet County, Kenya (−0.78, 35.34). The layout is synthetic.
- **Season:** 60 days, 4 visits a day, 5 working days a week. That covers every farm about once every 5 weeks. Travel time is ignored.
- **Fall armyworm:** each farm has a 0.2% daily chance, up to 3× higher in a warm, dry week. Weather risk varies by village and by week. The moths travel far, so a neighbour's case says nothing about your farm.
- **Maize lethal necrosis (MLN):** 2 first cases, plus a 0.05% background daily chance, plus 0.5% a day for each infected farm within 2 km. This is the case where "your neighbours have it" matters.
- **Farmer reports:** 40% of real problems are reported, 1–5 days after they start. There are also false alarms: 0.2% per farm per day.
- **Weather Fieldwise sees:** the true weather risk ± 0.2.
- **A problem counts as reached** if Felix visits that farm within 7 days of it starting. Problems starting in the last 7 days are not counted.

A typical season has about 21 fall armyworm farms, about 15 MLN farms, about 19 real reports and about 12 false ones.

## The three scheduling rules

| Rule | How it picks the day's 4 farms | What it knows |
|---|---|---|
| Basic rotation | Every farm in turn, village by village | Nothing |
| Experienced officer | Farms with an open report first (oldest first), then whoever has waited longest | Farmer reports |
| Fieldwise | Ranks farms by the chance of an unseen problem since the last visit, plus open reports | Reports, observed weather, known MLN nearby |

Fieldwise does **not** know the simulation's true rates. It uses its own rule-of-thumb weights:
- a 0.3% daily base risk;
- a warm, dry week doubles fall armyworm risk;
- each known MLN farm within 2 km multiplies MLN risk by 5;
- a farmer report is real half the time.

These weights are deliberately different from the true values above.

## Checks against overclaiming

1. **Paired runs.** All three rules face the identical 200 seasons. We report the average, a 5–95% range, and how many seasons Fieldwise won.
2. **Experienced-officer comparison.** Beating a basic rotation isn't enough, because a sensible officer already chases reports. Fieldwise has to beat that officer to show its data adds something.
3. **No-signal test.** Reports and weather are shuffled across farms and villages, so they no longer point at real problems. **Expected result: Fieldwise's lead disappears.** If it didn't, the win would come from the set-up rather than the data.
4. **Weight sensitivity.** Fieldwise reruns with its weather and neighbour weights halved and doubled. A result that holds only for one exact setting would be fragile.
5. **Scale.** The same tool with 100, 250 and 1,000 farms per officer, still at 4 visits a day. 100 farms reflects an agribusiness, co-op or NGO field officer. 1,000 reflects government ratios in Kenya and South Africa (Tshego's research).

## What we expected before running

- Fieldwise beats basic rotation with real signals.
- Fieldwise beats the experienced officer by a smaller margin. The officer uses reports, but ignores weather and nearby MLN.
- With scrambled signals, Fieldwise is no better than rotation.

## Changes after the first commit

The first committed version (846efb9) gave Fieldwise the simulation's true formulas. Before any comparison was run, it was replaced with separate rule-of-thumb weights. MLN neighbour spread was also halved after checking world statistics only (MLN had reached up to 52 of 100 farms in two months). No scheduling results had been seen at that point.

## Limitations

- Problems stay until visited. Real infestations change, and some become obvious to everyone.
- Travel time, road access and visit length are ignored.
- The rates are plausible assumptions, not estimates fitted to Bomet field data.
- Fieldwise's weights are fixed. In a pilot they would be learned from visit outcomes, as the Kasungu workspace already does.
