# Design references

Fieldwise borrows design decisions, not branding, from two farm apps.

## FarmRise (Bayer / The Climate Corporation, designed by Lollypop)

FarmRise won an A' Design Award in 2019. Lollypop's case study describes research with 150+ farmers in Karnataka and Maharashtra over three months. The farmers owned basic phones and mostly used the internet through them.

| FarmRise decision | What Fieldwise does |
|---|---|
| Key content up front, so users don't search for it | A **Visit first** card under the hero names the top-ranked farm, its reason and one button. |
| Tap only, because farmers weren't comfortable typing | **Visit outcome chips** (Wilting confirmed, Standing water, Follow up in 3 days…) fill the visit note with one tap. Check-in answers were already tap-only and now have 48px targets. |
| Light, familiar illustrations instead of photos | Each crop has a flat inline SVG drawing (`static/crops.js`): maize, groundnuts, tobacco and vegetables. They cost no extra requests and work offline. |
| Flat colour, white space, every element must justify itself | Glows, gradients and drop shadows were removed, and the space between sections increased. Action buttons lost their decorative ↗ arrows; external links keep them. |

## Climate FieldView

FieldView's field health maps use a colour index to flag areas that need attention. Fieldwise colours its Kasungu map pins the same way: clay for visit or call today, amber for watch, green for routine, grey for a recorded visit. A legend sits under the map.

## Copy

All interface text was checked with [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop), first in Detect mode, then against its `eval.md` checklist. The fixes covered slogan headlines, colon reveals, repeated binary contrasts ("not X"), the same disclaimer repeated four times on one page, decorative arrows, and plural and capitalisation errors.

## Sources

- [Lollypop: FarmRise case study](https://lollypop.design/projects/farmrise/)
- [A' Design Award: FarmRise listing](https://competition.adesignaward.com/ada-winner-design.php?ID=71284)
- [Climate FieldView: scouting with field health maps](https://climate.com/blog/five-ways-to-scout-more-efficiently-this-growing-season)
- [no-ai-slop on GitHub](https://github.com/petergyang/no-ai-slop)
