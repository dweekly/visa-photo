# United States — Department of State photo requirements, as retrieved 2026-09-06

Verbatim quotations from the official pages named below, fetched on that date through a real browser (travel.state.gov blocks scripted fetches); this file is provenance for the profiles in src/visaphoto/profiles.py and is not a summary.

# U.S. Photo Requirements — Verbatim Source Report

**All pages retrieved 2026-09-06** (via headless browser; `curl`/WebFetch are blocked by Cloudflare on travel.state.gov — anything scripted must use a real browser).

**Pages actually read** (two of the four requested URLs moved):

| Requested | Actually read |
|---|---|
| `/passports/how-apply/photos.html` | **redirects to** `https://travel.state.gov/en/passports/apply/help/photos.html` — "Passport Photos", *Last Updated: March 24, 2026* |
| `/passports/how-apply/photos/photo-composition-template.html` | **HTTP 404 — does not exist** |
| `/us-visas/.../photos.html` | same URL, "Photo Requirements" |
| `/us-visas/.../digital-image-requirements.html` | same URL, "Digital Image Requirements" |
| (found via navigation) | `/us-visas/.../photos/photo-composition-template.html` — "Photo Composition Template" |
| (found via navigation) | `/us-visas/.../photos/frequently-asked-questions.html` — "Photo Frequently Asked Questions" |
| (found via navigation) | `https://travel.state.gov/en/passports/renew-replace/online/upload-digital-photo.html` — "Uploading a Digital Photo", *Last Updated: May 04, 2026* |
| DS-160 photo tool | `https://tsg.phototool.state.gov/photo` — **contains no numeric specs**, only links |

---

## 1. Printed photo size, head size band, eye height band

**Heading: "Size and position"** — `https://travel.state.gov/en/passports/apply/help/photos.html`

> The correct printed size of a passport photo is 2 x 2 inches (51 x 51 mm).
> The size of your head in the printed photo must be between 1 -1 3/8 inches (25 - 35 mm) from the bottom of the chin to the top of the head.
> Your hair may extend past the edges of the photo, as long as your entire head is shown and is the appropriate size.

*(retrieved 2026-09-06)*

**Heading: "Your photos or digital images must be:"** — `https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos.html`

> Sized such that the head is between 1 inch and 1 3/8 inches (22 mm and 35 mm) or 50% and 69% of the image's total height from the bottom of the chin to the top of the head. View the Photo Composition Template for more size requirement details.

*(retrieved 2026-09-06)*

**Heading: "What size must my photos be?" / "How large should my head be in the photo?"** — `https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos/frequently-asked-questions.html`

> The photo must be exactly 2 x 2 inches (51 x 51 mm).

> Your head should be between 1 inch and 1-3/8 inches (between 25 and 35 mm) from the bottom of your chin to the top of your hair. If you are submitting a digital image, then your head should be between 50% and 69% of the image's total height from the top of the head, including the hair, to the bottom of the chin.

*(retrieved 2026-09-06)*

**Eye height** — exists **only inside images**, not as page text, on `https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos/photo-composition-template.html` (the page has zero body text; it is three JPEGs). Image `alt="Paper Photo Head Size Template"` reads:

> 2 inch · 2 inch · 1 inch to 1 3/8 inch · 1 1/8 inch to 1 3/8 inch

The `1 1/8 inch to 1 3/8 inch` dimension line runs from the bottom edge of the photo to the eye line. Image `alt="Digital Image Head Size Template"`:

> 600 px. · 600 px. · 50-69% · 56-69%

`56-69%` runs from the bottom edge to the eye line. **These are graphic labels, not sentences** — there is no prose statement of an eye-height band on any page read.

---

## 2. Digital image specifications

**Heading: "The digital image must adhere to the following specifications:"** — `https://travel.state.gov/content/travel/en/us-visas/visa-information-resources/photos/digital-image-requirements.html` (a table; each row is `Label⇥value`)

> **Dimensions** The image dimensions must be in a square aspect ratio (the height must be equal to the width). Minimum acceptable dimensions are 600 x 600 pixels. Maximum acceptable dimensions are 1200 x 1200 pixels. Please review photo requirements for specific dimensions.
> **Color** The image must be in color (24 bits per pixel) in sRGB color space which is the common output for most digital cameras.
> **File Format** The image must be in JPEG file format
> **File Size** The image must be less than or equal to 240 kB (kilobytes).
> **Compression** The image may need to be compressed in order for it to be under the maximum file size. The compression ratio should be less than or equal to 20:1.

**Heading: "Want to scan an existing photo?"** (same URL)

> In addition to the digital image requirements, your existing photo must be:
> 2 x 2 inches (51 x 51 mm)
> Scanned at a resolution of 300 pixels per inch (12 pixels per millimeter)

*(retrieved 2026-09-06)*

**Heading: "Additional Requirements for the Diversity Visa (DV) Program"** — `.../visa-information-resources/photos.html`

> In JPEG (.jpg) file format
> Equal to or less than 240 kB (kilobytes) in file size
> In a square aspect ratio (height must equal width)
> 600x600 pixels in dimension

**Photo tool**, same page, heading "Do you want to take the photo yourself?":

> crop it to a square image of exactly 600 x 600 pixels, and

*(retrieved 2026-09-06)*

**Passport online renewal is a different spec entirely.** Heading "Take and save your photo" — `https://travel.state.gov/en/passports/renew-replace/online/upload-digital-photo.html`

> The photo is a JPG, JPEG, PNG, HEIC, or HEIF file. Photos taken on a mobile device may automatically save in one of these formats.
> The file size should be between 54 KB and 10 MB.
> Do not take a photo of a printed photo or scan a physical photo to make a digital file.

*(retrieved 2026-09-06)*

**Resizing/upscaling** — heading "Digital changes", `.../apply/help/photos.html`:

> Do not stretch or compress your image to resize it.

---

## 3. Prohibition on digital alteration / retouching

**Heading: "Digital changes"** — `https://travel.state.gov/en/passports/apply/help/photos.html`

> Submit the original, unchanged photo.
> Do not change your photo using computer software, phone apps or filters, or artificial intelligence.
> We check all photos to ensure you are not using artificial intelligence tools.
> The image is an original but the background is not plain white or off-white. Do not enhance or change the photo using software or artificial intelligence tools. Fix your lighting and background and take a new photo.

**Heading: "Do you want to take the photo yourself?"** — `.../visa-information-resources/photos.html`

> Photos must not be digitally enhanced or altered to change your appearance in any way.

**Heading: "Can I remove the red-eye from my photo?"** — visa FAQ

> It is acceptable to use the red-eye reduction option on your digital camera when you are taking the photo. However, you cannot use any photo editing tool to digitally remove the red-eye from your photo. In general, you are not allowed to digitally enhance or alter the photo to change your appearance in any way.

*(retrieved 2026-09-06)*

---

## 4. Background, glasses, head coverings, expression, recency

**Background** — heading "Background", `.../apply/help/photos.html`:

> Background must be white or off-white, free of shadows, and plain without texture, objects, or lines.

Visa page, heading "Your photos or digital images must be:":

> Taken in front of a plain white or off-white background

**Glasses — the 2016 change.** The date appears **only** on the visa FAQ, heading "Can eyeglasses be worn for the photo?":

> Effective November 1, 2016, eyeglasses are no longer allowed in new visa photos, except in rare circumstances when eyeglasses cannot be removed for medical reasons; e.g., the applicant has recently had ocular surgery and the eyeglasses are necessary to protect the applicant's eyes.

The visa photos page carries the same sentence **without the date**: "Eyeglasses are no longer allowed in new visa photos, except in rare circumstances…". The passport page states the rule with no date at all, heading "Clothing, hats, and glasses":

> Take off any eyeglasses, sunglasses, or tinted glasses. Do not rest them on your head for the photo.

**Head coverings** — visa page:

> Do not wear a hat or head covering that obscures the hair or hairline, unless worn daily for a religious purpose. Your full face must be visible, and the head covering must not cast any shadows on your face.

Passport page, "Clothing, hats, and glasses":

> If you wear one for religious purposes, submit a signed statement that says it is religious attire worn daily in public.
> It should be one color
> The material should not have patterns or small holes

**Expression** — visa: "With a neutral facial expression and both eyes open". Passport, "Pose and expression":

> Avoid exaggerated facial expressions. You can smile in your photo. Just make sure your eyes are open and your mouth is closed.

Passport online renewal, "Pose and expression": "Use a neutral facial expression or natural smile. Avoid showing teeth."

**Recency** — visa: "Taken within the last 6 months to reflect your current appearance". Passport, heading "Use a photo taken within the last 6 months":

> Your passport photo needs to have been taken within the last 6 months.

*(all retrieved 2026-09-06)*

---

## 5. Measurable definitions — does "top of the head" include hair?

Only the visa FAQ defines it, under "How large should my head be in the photo?":

> …from the bottom of your chin to the **top of your hair**. …between 50% and 69% of the image's total height from the **top of the head, including the hair**, to the bottom of the chin.

The passport page says the opposite about framing, under "Size and position":

> Your hair may extend past the edges of the photo, as long as your entire head is shown and is the appropriate size.

*(retrieved 2026-09-06)*

---

## Contradictions found

1. **22 mm vs 25 mm — CONFIRMED, and it is a live conflict inside the visa section itself.** `.../visa-information-resources/photos.html` says "**1 inch and 1 3/8 inches (22 mm and 35 mm)**"; the visa FAQ one click away says "**1 inch and 1-3/8 inches (between 25 and 35 mm)**"; the passport page says "**1 -1 3/8 inches (25 - 35 mm)**". 1 inch = 25.4 mm, so the 22 mm figure is arithmetically inconsistent with its own inch value. Two of three official pages say 25.
2. **Passport page contradicts itself on the upper bound.** Body rule: "1 -1 3/8 inches (25 - 35 mm)". Its own photo tips repeatedly say "**between 1 inch and 1.4 inches (25 and 35 mm)**". 1 3/8 in = 1.375 in = 34.9 mm; 1.4 in = 35.6 mm.
3. **Hair.** Visa FAQ measures to the top of the hair; the passport page allows hair to extend past the photo edge.
4. **Digital specs are two incompatible regimes.** Visa/DS-160: JPEG only, 600×600–1200×1200, square, ≤240 kB. Passport online renewal: JPG/JPEG/PNG/HEIC/HEIF, 54 KB–10 MB, no pixel dimensions, no square requirement.
5. **Scanning.** Visa allows a scan at 300 ppi; both passport pages forbid scans outright ("Do not submit photocopies or digitally scanned photos").

## Not found on the pages read

- **Eye-height band as prose** — exists only as dimension labels inside the composition-template JPEGs (paper `1 1/8 inch to 1 3/8 inch`; digital `56-69%`). No sentence states it anywhere.
- **Any eye-height or head-height percentage on the passport pages** — not found on the pages read.
- **Pixel dimensions, aspect ratio, color depth, color space, or compression ratio for passport online renewal** — not found on the pages read.
- **The literal phrase "24-bit color"** — the official wording is "24 bits per pixel"; "24-bit color" was not found.
- **A passport-side photo composition template** — the URL returns HTTP 404.
- **A date for the passport-side glasses rule** — not found; only the visa FAQ carries "Effective November 1, 2016".
- **Any numeric spec on the DS-160 photo tool page** — it contains only navigation links.
