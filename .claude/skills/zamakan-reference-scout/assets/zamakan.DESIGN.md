---
version: alpha
name: ZAMAKAN
description: House style for ZAMAKAN (زمكان, "space-time") agency deliverables. Used for reference boards and decks when a client has no design system of its own.
colors:
  navy: "#14213D"
  paper: "#F6F6F2"
  white: "#FFFFFF"
  teal: "#0B7C7C"
  gold: "#8F650B"
  plum: "#6B4E8C"
  slate: "#5C6575"
  mist: "#DADDE3"
  primary: "{colors.navy}"
  secondary: "{colors.gold}"
  tertiary: "{colors.teal}"
  canvas: "{colors.paper}"
  surface-card: "{colors.white}"
  ink: "{colors.navy}"
  muted: "{colors.slate}"
  hairline: "{colors.mist}"
  surface-dark: "{colors.navy}"
  on-dark: "{colors.paper}"
  on-primary: "{colors.white}"
typography:
  display-lg:
    fontFamily: Instrument Serif
    fontSize: 44px
    fontWeight: 400
    lineHeight: 1.1
  headline-md:
    fontFamily: Instrument Serif
    fontSize: 26px
    fontWeight: 400
    lineHeight: 1.2
  body-md:
    fontFamily: IBM Plex Sans
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.55
  label-md:
    fontFamily: IBM Plex Sans
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1
    letterSpacing: 0.1em
  ar-headline-md:
    fontFamily: Reem Kufi
    fontSize: 24px
    fontWeight: 600
    lineHeight: 1.4
  ar-body-md:
    fontFamily: IBM Plex Sans Arabic
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.7
rounded:
  sm: 4px
  md: 6px
  pill: 20px
spacing:
  xs: 4px
  sm: 8px
  md: 14px
  lg: 20px
  xl: 44px
components:
  card:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: 18px
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.pill}"
  badge-direct:
    backgroundColor: "{colors.teal}"
    textColor: "{colors.white}"
    rounded: "{rounded.pill}"
  badge-category:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.white}"
    rounded: "{rounded.pill}"
  badge-adjacent:
    backgroundColor: "{colors.plum}"
    textColor: "{colors.white}"
    rounded: "{rounded.pill}"
  badge-wildcard:
    backgroundColor: "{colors.muted}"
    textColor: "{colors.white}"
    rounded: "{rounded.pill}"
  divider:
    backgroundColor: "{colors.hairline}"
    height: 1px
  meta-text:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.slate}"
  cover:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    typography: "{typography.display-lg}"
---

# ZAMAKAN (زمكان)

## Overview

The agency's own look for internal and pitch deliverables: reference boards, scout decks, reports. Calm, editorial and
bilingual. The work being shown is the hero; the frame stays quiet. Navy ink on warm paper, one teal accent for
links and the "direct" ring, gold and plum only to tell reference rings apart.

## Colors

- **Navy (#14213D)**: ink, cover slides, the dark band. Never a large light-on-dark body of text.
- **Paper (#F6F6F2)**: the page canvas. **White (#FFFFFF)**: cards sit on it.
- **Teal (#0B7C7C)**: the accent. Links, the "direct" ring, eyebrow labels on slides. Passes AA on paper.
- **Gold (#8F650B)** and **Plum (#6B4E8C)**: ring badges only (category, adjacent). Not for text blocks.
- **Slate (#5C6575)**: secondary text, metadata. **Mist (#DADDE3)**: hairlines and borders.

## Typography

- **Instrument Serif** for display and headings (Latin). Large, regular weight, tight leading.
- **IBM Plex Sans** for body, labels, tables. Labels are uppercase with 0.1em tracking.
- **Reem Kufi** for Arabic headings (territory names), **IBM Plex Sans Arabic** for Arabic body. Arabic is always set
  right-to-left in its own block, never mixed inline into an English line.

## Layout

A single column up to 1240px with 20px gutters, sections 44px apart. Reference grids use cards of at least 250px.
Decks are 16:9 with a 2cm margin; one idea per slide.

## Elevation & Depth

Flat. Cards are separated by a 1px mist hairline, not shadows.

## Shapes

Cards 6px radius, thumbnails 4px, badges and filter buttons are pills.

## Components

- **card**: white, hairline border, 6px radius, 18px padding.
- **button-primary**: navy pill with white label text.
- **badge-***: one colour per reference ring (teal direct, gold category, plum adjacent, slate wildcard).
- **divider** / **meta-text**: mist hairlines; slate metadata on paper.
- **cover**: navy slide with paper text and a display headline.

## Do's and Don'ts

- Do let campaign images carry the colour; keep the frame neutral.
- Do put the Arabic name under the English one, right-aligned.
- Don't use gold or plum for running text.
- Don't add drop shadows or gradients.
