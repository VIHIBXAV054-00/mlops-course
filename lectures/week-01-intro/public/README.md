# Deck assets (served verbatim)

Slidev serves everything here at the deck root, so `public/zillow.png` is referenced from
a slide as `/zillow.png`. Files here are not processed by the bundler.

## zillow.png

Screenshot of the Zillow Offers product page, used on the Week 1 cold-open slide to show
what the product was before the failure is explained.

Zillow, Zestimate and the Zillow logo are trademarks of Zillow Group, Inc. The screenshot
is reproduced to illustrate a documented public business case; the slide carries that
credit. This repository's CC BY 4.0 licence covers the course's own text and diagrams —
**it does not extend to this image or to the marks in it**, so do not treat it as
re-licensable material.

## Adding another image

Drop the file here and reference it from a slide as `/<filename>`. One caveat worth
knowing: Slidev turns an img src into a bundler import, so a **missing** file fails the
build with `UNRESOLVED_IMPORT` rather than degrading. If you want a slide that still
builds when an image is absent, load it as a CSS `background-image` instead.
