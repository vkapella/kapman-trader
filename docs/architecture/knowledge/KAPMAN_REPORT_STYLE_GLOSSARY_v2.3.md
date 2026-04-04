KAPMAN_REPORT_STYLE_GLOSSARY_v2

KapMan visual specification for HTML trading reports.
Pure visual and CSS rules only. All behavioral rules, content models, and section ordering live in KAPMAN_PROJECT_INSTRUCTIONS_v2.

---

TYPOGRAPHY

| Element              | Size    | Weight | Align   | Other                     |
|----------------------|---------|--------|---------|---------------------------|
| body                 | 7.8pt   | normal | —       | Arial, sans-serif         |
| title (h1)           | 10.5pt  | bold   | center  | letter-spacing .5px       |
| subtitle (.subtitle) | 7pt     | normal | center  | color #444                |
| section header       | 8pt     | bold   | left    | white on dark bg          |
| table header (th)    | 6.8pt   | bold   | center  | white on blue bg, nowrap  |
| table cell (td)      | 7pt     | normal | —       | line-height 1.25          |
| badge (.tag)         | 6.5pt   | bold   | —       | inline-block, nowrap      |
| legend/footer        | 6.5pt   | normal | —       | color #555                |
| footnote             | 6.5pt   | normal | —       | color #444                |
| source bar           | 6.5pt   | normal | —       | color #555, green left border |

---

SPACING

| Element              | Value                   |
|----------------------|-------------------------|
| page padding         | 10px 12px               |
| print padding        | 6px 8px                 |
| section header pad   | 2px 6px                 |
| section margin       | 5px top, 2px bottom     |
| table header pad     | 2px 3px                 |
| table cell pad       | 1.5px 3px               |
| table margin-bottom  | 4px                     |
| two-col gap          | 8px                     |
| badge pad            | 0 4px                   |
| legend padding-top   | 3px                     |
| legend margin-top    | 4px                     |

---

COLORS

| Role                 | Value   | Usage                              |
|----------------------|---------|------------------------------------|
| body text            | #111    | default                            |
| muted text           | #444    | subtitles, secondary               |
| gray text            | #666    | notes, low-priority                |
| section header bg    | #1a1a2e | dark nav bar                       |
| section header text  | #fff    | —                                  |
| table header bg      | #2c3e6b | column headers                     |
| table header text    | #fff    | —                                  |
| zebra stripe         | #f7f8fc | even rows                          |
| row border           | #e0e0e0 | cell bottom border                 |
| legend border        | #ccc    | top border above footer            |
| footnote border      | #ccc    | dashed top border                  |

---

SEMANTIC ROW BACKGROUNDS

Apply to entire <tr> via class. Use !important to override zebra.

| Class     | Background | Use When                                      |
|-----------|------------|-----------------------------------------------|
| .act      | #fff3cd    | ACT TODAY — position needs action now          |
| .urgent   | #fde8e8    | URGENT — stop triggered, worst position, exit  |
| .good     | #eafaf1    | GOOD — profitable, above flip, on track        |
| .warn     | #fff8e1    | WARNING — risk flag, caution, approaching stop |
| .monitor  | #f0f4ff    | MONITOR — deferred entry, watching             |
| .cond     | #f3e8ff    | CONDITIONAL — blocked, needs trigger           |

Use color semantically, not decoratively. Every row gets ONE class based on its action priority.

---

SEMANTIC TEXT COLORS

| Class    | Color   | Weight | Use When                                   |
|----------|---------|--------|--------------------------------------------|
| .red     | #c0392b | bold   | negative P/L, stop levels, broken, loss    |
| .green   | #1a7a3c | bold   | positive P/L, above flip, supportive, gain |
| .orange  | #d35400 | bold   | caution, approaching threshold             |
| .blue    | #1a4fa0 | bold   | informational emphasis                     |
| .gray    | #666    | normal | secondary notes, N/A fields                |

---

BADGE TAGS

All badges: inline-block, padding 0 4px, border-radius 2px, font-size 6.5pt, bold, nowrap.

| Class       | Background | Text    | Example Labels                        |
|-------------|------------|---------|---------------------------------------|
| .tag-red    | #fde8e8    | #c0392b | Below flip, EXIT, STOP, Weak chain    |
| .tag-green  | #eafaf1    | #1a7a3c | Above flip, ACT, Full chain, HOLD     |
| .tag-orange | #fff3cd    | #a04000 | MONITOR, Near flip, CONDITIONAL       |
| .tag-gray   | #f0f0f0    | #555    | N/A, Low conf, Needs validation       |
| .tag-blue   | #e8f0fe    | #1a4fa0 | Candidate zone, Info                   |
| .tag-purple | #f3e8ff    | #6b21a8 | Ranked conditional (#1, #2, #3)        |

Common badge labels:
Above flip / Below flip / Near flip
Full chain / Limited chain / Weak chain
ACT / MONITOR / CONDITIONAL / URGENT / HOLD / TRIM / EXIT
Candidate zone / Needs validation
High / Med / Low (confidence)
#1 PICK / #2 / #3 (ranking)

---

TABLE RULES

- width: 100%
- border-collapse: collapse
- compact row height
- bold centered headers
- thin border-bottom on body cells (1px solid #e0e0e0)
- vertical-align: middle
- line-height: 1.25
- zebra on even rows (#f7f8fc)
- left-align long text cells (rationale, action, notes)
- center-align short data cells (spot, DGPI, DTE, conf)

---

COLUMN WIDTH CONSTRAINTS

| Column Type     | Max Width | Notes                                    |
|-----------------|-----------|------------------------------------------|
| rationale-col   | 180px     | Hard cap. Overflow goes to footnotes.    |
| action-col      | 165px     | For portfolio ACT table action field.    |
| stop-col        | 50px      | Underlying price only.                   |
| scale-col       | 70px      | Two levels max: "$119→50% / $120→close"  |
| note-col        | 150px     | For HOLD/MONITOR table note field.       |

---

TWO-COLUMN LAYOUT

- display: grid
- grid-template-columns: 1fr 1fr
- gap: 8px
- margin-top: 4px

Used for sidebar sections below the main table (alerts, discards, risks, dealer snapshot, WoW changes, equities, checklist).

---

FOOTNOTE SECTION

For rationale overflow. Superscript numbers (¹²³) in rationale cells link to expanded notes.

- font-size: 6.5pt
- color: #444
- border-top: 1px dashed #ccc
- padding-top: 2px
- margin-top: 2px
- placed between main content and legend

---

SOURCE BAR

Data quality attestation bar placed immediately below the subtitle.

- font-size: 6.5pt
- color: #555
- background: #f0f7f0
- border-left: 3px solid #2c5e2c
- padding: 2px 6px
- margin: 0 0 2px 0

---

LEGEND / FOOTER

- font-size: 6.5pt
- color: #555
- margin-top: 4px
- border-top: 1px solid #ccc
- padding-top: 3px

Must include:
1. Data sources and timestamps
2. Rule ID references (the ONLY place rule IDs appear)
3. Key definitions (Stop = underlying close price; Scale = staged exit)
4. Any data quality caveats

---

PRINT

- @page size: landscape
- margins: 0.35in 0.3in
- body padding: 6px 8px
- target: one page or near-one-page
- avoid long narrative and whitespace
- no background colors in print unless using -webkit-print-color-adjust: exact

---

REFERENCE CSS

```css
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:Arial,sans-serif;font-size:7.8pt;color:#111;background:#fff;padding:10px 12px;}
h1{font-size:10.5pt;font-weight:bold;text-align:center;letter-spacing:.5px;margin-bottom:3px;}
.subtitle{text-align:center;font-size:7pt;color:#444;margin-bottom:6px;}
.source-bar{font-size:6.5pt;color:#555;background:#f0f7f0;border-left:3px solid #2c5e2c;padding:2px 6px;margin:0 0 2px 0;}
.section-title{font-size:8pt;font-weight:bold;background:#1a1a2e;color:#fff;padding:2px 6px;margin:5px 0 2px 0;letter-spacing:.4px;}
table{width:100%;border-collapse:collapse;margin-bottom:4px;}
th{background:#2c3e6b;color:#fff;font-size:6.8pt;font-weight:bold;padding:2px 3px;text-align:center;white-space:nowrap;}
td{font-size:7pt;padding:1.5px 3px;border-bottom:1px solid #e0e0e0;vertical-align:middle;line-height:1.25;}
tr:nth-child(even) td{background:#f7f8fc;}
.act{background:#fff3cd!important;}
.urgent{background:#fde8e8!important;}
.good{background:#eafaf1!important;}
.warn{background:#fff8e1!important;}
.monitor{background:#f0f4ff!important;}
.cond{background:#f3e8ff!important;}
.red{color:#c0392b;font-weight:bold;}
.green{color:#1a7a3c;font-weight:bold;}
.orange{color:#d35400;font-weight:bold;}
.blue{color:#1a4fa0;font-weight:bold;}
.gray{color:#666;}
.tag{display:inline-block;padding:0 4px;border-radius:2px;font-size:6.5pt;font-weight:bold;white-space:nowrap;}
.tag-red{background:#fde8e8;color:#c0392b;}
.tag-green{background:#eafaf1;color:#1a7a3c;}
.tag-orange{background:#fff3cd;color:#a04000;}
.tag-gray{background:#f0f0f0;color:#555;}
.tag-blue{background:#e8f0fe;color:#1a4fa0;}
.tag-purple{background:#f3e8ff;color:#6b21a8;}
.rationale-col{max-width:180px;}
.action-col{max-width:165px;}
.note-col{max-width:150px;}
.stop-col{max-width:50px;}
.scale-col{max-width:70px;}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:4px;}
.footnote{font-size:6.5pt;color:#444;border-top:1px dashed #ccc;padding-top:2px;margin-top:2px;}
.legend{font-size:6.5pt;color:#555;margin-top:4px;border-top:1px solid #ccc;padding-top:3px;}
@media print{body{padding:6px 8px;}@page{size:landscape;margin:.35in .3in;}}
</style>
```

---

VERSION

| Date       | Version | Change                                                |
|------------|---------|-------------------------------------------------------|
| 2026-03-01 | 1.0     | Initial glossary (ChatGPT draft)                      |
| 2026-03-08 | 2.0     | Split behavioral content to INSTRUCTIONS. Added footnote, source-bar, rationale-col CSS. Removed CONTENT MODEL, CONTRACT RULES, SCREENING PRIORITIES, PORTFOLIO PRIORITIES, DECLUTTER sections (moved to INSTRUCTIONS). |
| 2026-04-04 | 2.3 | Standardized to v2.3 production baseline. No content changes. |
