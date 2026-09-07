# Schengen — EU, ICAO Doc 9303, France and Germany photo requirements, as retrieved 2026-09-06

Verbatim quotations from the official pages and PDFs named below, fetched on that date; this file is provenance for the profiles in src/visaphoto/profiles.py and is not a summary.

# Schengen Visa Photo Requirements — Verbatim Source Survey
All pages/PDFs fetched **2026-09-06**.

---

## 1. European Commission — "Photograph quality" guidance sheet

**URL:** `https://home-affairs.ec.europa.eu/document/download/5bb16566-c8c2-4afb-b038-530f488cb72a_en?filename=icao_photograph_guidelines_en.pdf` — retrieved 2026-09-06 (HTTP 200, 448 KB, 3 pp.)

Every numeric statement in the document, verbatim (section "Photograph quality"):

> The photographs must be:
> ■ no more than 6-months old
> ■ 35–40mm in width

> ■ close up of your head and top of your shoulders so that your face takes up 70–80% of the photograph

Non-numeric but relevant (sections "Style and lighting", "Glasses and head covers"):

> ■ be taken with a plain light-coloured background

> ■ are not permitted except for religious reasons, but your facial features from bottom of chin to top of forehead and both edges of your face must be clearly shown.

**Those are the only numbers in the document.** Grep for `mm|dpi|pixel|resolution|%|month` returns exactly the three quoted above plus the non-numeric words "high resolution" and "pixelated".

**Provenance caveat (verify, don't assume):** PDF metadata reads `Title: Brochure (Terry_variant)`, `Author: Deborah Frankham`, `Creator: QuarkXPress: LaserWriter 8`, `CreationDate: 2003-04-07`, `ModDate: 2015-03-25`. It is served from the Commission's domain but is a 2003-authored brochure of apparent UK origin, carrying no EU branding or date. I could not find a Commission landing page that links it: `https://home-affairs.ec.europa.eu/policies/schengen-borders-and-visa/visa-policy_en` contains no photograph guidance link.

---

## 2. Visa Code — Regulation (EC) No 810/2009, Article 13(4)

**URLs:** original `https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32009R0810`; consolidated `https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:02009R0810-20200202` — both retrieved 2026-09-06.

Article 13 "Biometric identifiers", paragraph 4, second subparagraph — **identical in both texts**:

> The technical requirements for the photograph shall be in accordance with the international standards as set out in the International Civil Aviation Organization (ICAO) document 9303 Part 1, 6th edition.

Preceding subparagraph, for context:

> In accordance with Article 9(5) of the VIS Regulation, the photograph attached to each application shall be entered in the VIS. The applicant shall not be required to appear in person for this purpose.

The Regulation states **no** dimensions, proportions, pixel counts or DPI. The reference points to **Part 1, 6th edition** — see contradictions below.

---

## 3. ICAO Doc 9303 Part 3 — Eighth Edition, 2021

**URL:** `https://www.icao.int/sites/default/files/publications/DocSeries/9303_p3_cons_en.pdf` — retrieved 2026-09-06. Title page: `Doc 9303 / Machine Readable Travel Documents / Eighth Edition, 2021 / Part 3: Specifications Common to all MRTDs`.

**Doc 9303 Part 3 does state a numeric ratio itself** — the premise that it only defers to a Technical Report is **incorrect**. §3.9.1.3, "Portrait placement in an MRTD and coexistence with security printing":

> The printed portrait shall be centred within Zone V, with the crown (top of the head ignoring any hair) nearest the top edge of the MRTD. The crown-to-chin portion of the facial image shall be 70 to 80 per cent of the longest dimension defined for Zone V, maintaining the aspect ratio between the crown-to-chin and ear-to-ear details of the face of the holder. The 70 to 80 per cent requirement may mean cropping the picture so that not all the hair is visible.

Other numerics, §3.9.1.1 "Image Printing for Portrait Submission":

> Submitted portraits should have a minimum width of 35 mm. The inter eye distance (IED) should be at least 10 mm.

> The quality of the original captured image should at least be comparable to the minimum quality acceptable for paper photographs (resolution comparable to 6 – 8 line pairs per millimetre).

§3.9.1.2 "Scanning of Submitted Portraits":

> Properties of the submitted portrait. Submitted portraits should be 45.0 mm x 35.0 mm (1.77 in x 1.38 in) in dimension.

> A submitted portrait shall have been captured within the last six months before application, as outlined in [ISO/IEC 39794-5]. Portraits with a capture time dating back more than three months should not be accepted.

> The width to height ratio of the final image is defined by the application process of the issuer, a typical value is 7:9.

> A typical printed image with 10 mm IED should be scanned at a sampling rate of at least 300 ppi.

Deferral clauses — Part 3 refers to **ISO/IEC 39794-5**, *not* to the ICAO Technical Report on Portrait Quality (which is **not cited anywhere** in Part 3; the only "TECHNICAL REPORT" string in the document concerns Arabic font translation):

> Pixel count and Modulation Transfer Function (MTF). The final scanned images shall have a pixel count as specified in [ISO/IEC 39794-5].

> The photograph shall comply with the appropriate definitions set out in [ISO/IEC 39794-5].

---

## 4. France-Visas — FAQ, English and French

**EN URL:** `https://france-visas.gouv.fr/en/faq` — retrieved 2026-09-06. Question *"What is the format of the ID photographs I have to provide ?"*:

> The picture must be recent and conform to reality. **The photo should be between 35 and 40 mm wide**.  The size of the face should be 32 to 36 mm (70 to 80% of the picture) from chin to forehead (excluding hair) and comply with the ICAO standard.

**FR URL:** `https://france-visas.gouv.fr/fr/faq` — retrieved 2026-09-06. Question *"Quel est le format des photographies d'identité que je dois fournir ?"*:

> La prise de vue doit être récente et ressemblante au jour du dépôt de la demande et du retrait du titre. **La photo doit mesurer entre 35 et 40 mm de large**. La taille du visage doit être de 32 à 36 mm (soit 70 à 80% du cliché) du bas du menton au sommet du crâne (hors chevelure) et respecter la norme OACI.

**The reported discrepancy is CONFIRMED.** EN "from chin to forehead"; FR "du bas du menton au sommet du crâne" (from the bottom of the chin to the top of the skull). Both exclude hair; both give **32 to 36 mm** and **70 to 80%**.

---

## 5. Germany — Fotomustertafel (BMI / Bundesdruckerei)

**URL:** `https://www.bundesdruckerei-gmbh.de/files/dokumente/pdf/fotomustertafel.pdf` — retrieved 2026-09-06. Document footer: `Bundesministerium des Innern, 11014 Berlin, www.bmi.bund.de | Stand: Juli 2025 | Artikelnummer: BMI24037`. (The BMI-hosted copy `BMI24037-fotomustertafel.pdf` returned HTTP 400 "Zugriff nicht möglich".)

> Das Foto zeigt das Gesicht von der Kinnspitze bis zum oberen Kopfende. Beide Gesichtshälften sind deutlich erkennbar. Das Gesicht nimmt 70 bis 80 % der Höhe des Fotos ein.

Children ("Kinder"):

> Das Gesicht nimmt 50 bis 80 % der Höhe des Fotos ein. Bis zum vollendeten 10. Lebensjahr sind im Übrigen kleinere Abweichungen zulässig.

Head coverings:

> Kopfbedeckungen sind nur aus religiösen Gründen zulässig. In diesen Fällen gilt: Das Gesicht ist von der unteren Kinnkante bis zur Stirn sichtbar.

**No head-height in mm and no eye-position range appear in this document** — grep for `mm|dpi|Pixel|Auflösung|%` returns only the two percentage statements above.

---

## (a) Contradictions between sources

1. **Stale legal reference.** Art. 13(4) binds photos to *"ICAO document 9303 Part 1, 6th edition"*. Doc 9303 is now in its **8th Edition (2021)**, and the portrait specifications live in **Part 3**, not Part 1. The consolidated text (as amended to 2020-02-02) still carries the old citation.
2. **Different referent for 70–80%.** ICAO applies it to the **printed portrait inside Zone V of the finished document** ("70 to 80 per cent of the longest dimension defined for Zone V"). The EC sheet, France and Germany apply it to the **submitted photograph**. These are not the same measurement.
3. **Internal ICAO conflict on recency**, one sentence apart: "captured within the last six months" vs. "capture time dating back more than three months should not be accepted."
4. **Width.** EC and France give a **range** (35–40 mm); ICAO gives a **fixed** 45.0 × 35.0 mm plus a 35 mm *minimum* width. A 40 mm-wide photo satisfies the EC/France text but is not the ICAO size.
5. **What is measured.** France EN "chin to **forehead**" vs France FR "sommet du **crâne**" vs ICAO "**crown**-to-chin (top of the head ignoring any hair)" vs Germany "Kinnspitze bis zum **oberen Kopfende**". The French, German and ICAO wordings agree; the **English France-Visas text is the outlier** — "forehead" describes a smaller span than "top of skull", so 32–36 mm measured per the EN wording yields a materially larger head.
6. **Children.** Germany allows 50–80%; no other source read carries a child-specific proportion.

## (b) Not found on the pages read

- Any pixel dimensions or DPI for an applicant-submitted Schengen visa photo, at EU level — **not found**. (ICAO's 300 ppi and MTF figures govern the *issuer's scanner*, and pixel count is delegated to ISO/IEC 39794-5, which I did not fetch.)
- A head height in millimetres in any **EU-level** source — **not found**.
- Eye-position ranges in the German Fotomustertafel — **not found**.
- A head height in mm in the German Fotomustertafel — **not found**.
- A Commission landing page linking the "Photograph quality" sheet — **not found**.
- Background colour in ICAO Doc 9303 Part 3 — **not found** in the portrait sections read.

## (c) Does any EU-level source state a numeric head-height, pixel size or DPI?

**No.** Across the three EU-level sources read today — Regulation (EC) No 810/2009 Art. 13(4) (original and consolidated) and the Commission's "Photograph quality" sheet — the complete set of numbers is: *no more than 6-months old*, *35–40mm in width*, and *face takes up 70–80% of the photograph*. The Regulation itself contains no figures at all and defers wholly to ICAO Doc 9303 Part 1, 6th edition. No EU instrument states a head height in millimetres, a pixel dimension, or a DPI value. The 32–36 mm head height is a **French national** specification (France-Visas), and the 300 ppi figure is an **ICAO** scanning guideline for issuing authorities, not an EU requirement on applicants. A tool encoding these rules should attribute the millimetre head height to France, not to the EU.
