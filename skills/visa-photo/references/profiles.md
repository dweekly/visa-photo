# Profiles

`visa-photo --list-specs` is authoritative. Every rule quotes the sentence it applies, with its
page and retrieval date; the quotations are kept verbatim under `docs/sources/` in the
repository. Where a sentence defines nothing, the reading applied is on the rule
(`interpretation`) and printed in every report.

| key | destination and channel | what it does |
|---|---|---|
| `cn_visa_digital` | China, online visa application | crops, writes, checks. 354x472 (420x560 listed but the pixel rules are stated at 354x472 and not scaled). JPEG, "40 KB - 120 KB" under both readings of KB. Face width, crown gap, eye line, inter-eye distance. |
| `cn_visa_paper` | China, paper photo | plans only. 33x48 mm; head height, head width, crown gap, chin-to-bottom in mm. |
| `us_visa_digital` | United States, DS-160 digital image | crops, writes, checks. Square, 600x600 first then 1200x1200; head 50-69% and eye line 56-69% of image height (the latter from a label on the composition-template graphic); JPEG <= 240 kB, 24-bit sRGB checked from the file, 20:1 compression cap enforced as a byte floor. |
| `us_passport_print` | United States, printed passport photo | plans only. 2x2 in; head 25-35 mm (the visa page's "22 mm" recorded as a conflict), eye line from the visa-side template, both borrowings named as interpretations. |
| `nz_nzeta` | New Zealand, NZeTA and online visa photo | crops, writes, checks. 3:4 from 900x1200 to 2250x3000, largest first; JPG; two INZ pages give different byte bands and both are kept under both readings of KB; head 70-80% under the reading "face covers 70-80% of the image" = hair-inclusive head height over image height. Background replacement prohibited on INZ's own sentence. |
| `vn_evisa` | Vietnam, e-visa (evisa.gov.vn) | crops, writes, checks. 600x900 (the portal states only "4x6 cm", read as 2:3; any 2:3 size passes); JPEG under 2 MB under both readings of MB. **No published geometry**: the framing (head 60-70% of image height, eye line 30-50% from the top, both from ICAO Portrait Quality Table 9) is this tool's preference, never a criterion. |
| `schengen_print` | Schengen area, printed visa photo | refuses to crop, with the reason, and advises. No EU-level rule defines the head size; the ICAO rule the sources reach governs the printed portrait inside the finished document. |

## Readings and conflicts to report when they apply

- New Zealand's head rule is an interpretation; say so when reporting it.
- China's "> 60 pixels" and "> 256 pixels" are strict; a value on the bound fails.
- The US visa page says "22 mm" where 1 inch is 25.4 mm; the fraction rule is applied.
- New Zealand's two byte bands: a file inside 524,288-3,000,000 bytes satisfies every reading.
- Portraits with little margin above or beside the head cannot satisfy the US square: the
  plan exits 4 naming the conflicting rules. Report the refusal; do not pad the image.

- Vietnam states no head size or placement; say that the framing is the tool's preference and that only the frame and the file were checked against Vietnam's rule.

## What no profile can check

Background colour, borders, sharpness, exposure, skin tone, head coverings, when the photo was
taken, whether it is a photo of a photo. These appear in `not_assessable` and `attestations`.
