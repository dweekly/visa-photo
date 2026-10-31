# Vietnam — e-visa portal photo requirements, as retrieved 2026-10-31

Verbatim quotations from the official portal, read in a browser on that date (the portal's
certificate chain did not verify from a plain HTTPS client); this file is provenance for
`vn_evisa` in src/visaphoto/profiles.py and is not a summary.

## Sources

| Key | Page | URL |
|---|---|---|
| **A** | Instruction: guide to using the electronic visa application system | `https://evisa.gov.vn/instruction` |
| **B** | The e-visa application form, label on the portrait upload field (as the applicant sees it) | `https://evisa.gov.vn/` → Apply now |

## The portrait

**A**, under *Guide to entering visa declaration information*, Step 1:

> Step 1: Upload a portrait and biometric passport photo. After uploading the photos, the system will automatically display personal information from the passport. Users can check and update any incorrect information. Note: The visa applicant's photo must be a recent 4x6 cm image in JPG or JPEG format, with a file size of less than 2MB. The photo should be a front-facing image with no hat, no glasses, in formal attire, and with a white background.

> Step 2.1: The system automatically verifies the portrait and passport images. If valid, the system will automatically fill in the passport information fields.

> Step 2.2: If the passport photo is invalid, the system will not allow users to submit the application.

**B**, the upload field's label:

> Photo of the person requesting an electronic visa (newly taken, photo size 4x6 cm, jpg, jpeg format, size <2MB, straight face, no hat, no glasses, formal clothes, white background). Only upload 1 passport data page, upload clear photos, no lost corners *

## What neither page states

Reviewed: A in full and B's label. No pixel dimensions, no head size or proportion, no eye
line, no placement, no colour space, no minimum file size, no rule on editing or background
replacement, and no glasses or head-covering exception. "Recent", "newly taken" and "formal
attire" are not defined. Third-party guides give other figures (1 MB, 2048 KB, 472x709 px);
none appears on the portal.
