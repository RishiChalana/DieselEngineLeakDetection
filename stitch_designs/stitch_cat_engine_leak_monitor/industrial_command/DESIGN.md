---
name: Industrial Command
colors:
  surface: '#171309'
  surface-dim: '#171309'
  surface-bright: '#3e392c'
  surface-container-lowest: '#110e05'
  surface-container-low: '#1f1b10'
  surface-container: '#231f14'
  surface-container-high: '#2e2a1e'
  surface-container-highest: '#393428'
  on-surface: '#ebe2cf'
  on-surface-variant: '#d1c6ab'
  inverse-surface: '#ebe2cf'
  inverse-on-surface: '#353024'
  outline: '#9a9077'
  outline-variant: '#4d4632'
  surface-tint: '#edc200'
  primary: '#fff1ce'
  on-primary: '#3c2f00'
  primary-container: '#ffd100'
  on-primary-container: '#6f5a00'
  inverse-primary: '#725c00'
  secondary: '#c8c6c5'
  on-secondary: '#303030'
  secondary-container: '#474746'
  on-secondary-container: '#b6b5b4'
  tertiary: '#d0f9ff'
  on-tertiary: '#00363c'
  tertiary-container: '#0bebff'
  on-tertiary-container: '#006670'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffe07f'
  primary-fixed-dim: '#edc200'
  on-primary-fixed: '#231b00'
  on-primary-fixed-variant: '#564500'
  secondary-fixed: '#e4e2e1'
  secondary-fixed-dim: '#c8c6c5'
  on-secondary-fixed: '#1b1c1c'
  on-secondary-fixed-variant: '#474746'
  tertiary-fixed: '#8df2ff'
  tertiary-fixed-dim: '#00dbed'
  on-tertiary-fixed: '#001f23'
  on-tertiary-fixed-variant: '#004f56'
  background: '#171309'
  on-background: '#ebe2cf'
  surface-variant: '#393428'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: '1.2'
  metric-lg:
    fontFamily: JetBrains Mono
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: -0.01em
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.05em
  body-fixed:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-std:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
spacing:
  unit: 4px
  gutter: 16px
  margin-mobile: 16px
  margin-desktop: 32px
  panel-gap: 8px
---

## Brand & Style

The design system is engineered for high-stakes industrial environments where legibility, durability, and immediate data recognition are paramount. The brand personality is rugged, authoritative, and unapologetically technical, reflecting the physical strength of heavy machinery.

The aesthetic follows a **Hard-Edge Industrial** style. It rejects modern softness in favor of sharp 90-degree corners, high-contrast interfaces, and a "monolithic" structural feel. This ensures that operators can navigate complex telemetry data under harsh lighting conditions or high-vibration environments. The visual language is defined by precision engineering, utilizing thin 1px borders to define functional zones without adding visual bulk.

## Colors

The palette is anchored by "CAT Yellow," used strategically as a functional signal for primary actions and active states. 

- **Core Tones:** The primary background is a deep black to maximize contrast and reduce eye strain in low-light cabins. Panels use a slightly lighter charcoal to create structural separation.
- **Accents:** Borders and dividers utilize dark grays (#2A2A2A) to maintain a technical, schematized look.
- **Status:** Status colors are vibrant and high-saturation to ensure alerts are impossible to miss against the dark UI.
- **Application:** Use solid fills for critical alerts and 1px strokes for secondary data visualization.

## Typography

This design system employs a dual-font strategy to balance rapid legibility with technical precision.

- **Inter:** Used for all structural labels, headers, and UI controls. Heavy weights (600/700) and Uppercase styling are the default for technical metrics to evoke an industrial "stenciled" feel.
- **JetBrains Mono:** Reserved for all dynamic data, telemetry values, and coordinate systems. The monospaced nature ensures that jumping numbers do not cause layout shifts and remain readable during rapid fluctuations.
- **Scaling:** Font sizes are oversized compared to consumer apps to account for operator distance from the mounted HMI display.

## Layout & Spacing

The layout is built on a strict **12-column fixed grid** that prioritizes "Control Zones." 

- **Modular Panels:** Content is housed in distinct rectangular panels. Each panel is separated by an 8px gap, creating a clear "dashboard" architecture.
- **Density:** High information density is preferred. Use a 4px base unit for internal padding to keep elements tightly packed and professional.
- **Responsiveness:** On mobile/tablet HMI units, the 12-column grid collapses into a single-column scroll, but panel headers remain persistent to provide context.
- **Touch Targets:** Despite the tight visual spacing, all interactive buttons must maintain a minimum 48px height for gloved-hand interaction.

## Elevation & Depth

This system avoids shadows entirely to maintain a flat, rugged digital aesthetic. Depth is achieved through **Tonal Layering** and **High-Contrast Outlines**:

- **Level 0 (Base):** #0A0A0A for the global background.
- **Level 1 (Panels):** #1A1A1A for containers, defined by a 1px solid border (#2A2A2A).
- **Level 2 (Inputs/Inlays):** #0D0D0D for nested areas like charts or text input fields, creating a "carved-in" look.
- **Active State:** Focus is indicated by a 1px solid #FFD100 border or a full color fill; there are no soft blurs or glows.

## Shapes

The shape language is defined by **Absolute Geometry**. 

- **Corner Radius:** Strictly 0px. This applies to buttons, cards, checkboxes, badges, and the UI container itself. 
- **Precision:** Use 1px stroke widths for all borders. 
- **Visual Weight:** Heavy, solid blocks of color are used for primary interactions to contrast against the thin wireframe-style aesthetic of the rest of the interface.

## Components

### Buttons
- **Primary:** Solid #FFD100 background with #0A0A0A bold uppercase text. No border.
- **Secondary:** Transparent background with a 1px #FFD100 border and #FFD100 text.
- **Destructive:** Solid #FF3B30 background with white text, used only for E-Stop or critical resets.

### Inputs & Controls
- **Text Fields:** Background #0D0D0D with a #333333 border. Upon focus, the border switches to #FFD100.
- **Checkboxes/Radios:** Square 20px boxes. Checked state uses a solid #FFD100 fill with a black checkmark/inset square.
- **Progress Bars:** Flat, no-radius tracks using #2A2A2A. The fill is solid #FFD100 for normal operation, switching to status colors for warnings.

### Data Displays
- **Value Readouts:** Large JetBrains Mono text. Always include the unit (e.g., RPM, PSI) in a smaller Inter Bold Uppercase label immediately adjacent or below.
- **Gauges:** Linear or radial, using 1px increments. Avoid skeuomorphic dials; use clean, needle-based or segment-based digital indicators.

### Cards & Panels
- All panels must have a header area with a #2A2A2A bottom border. Headers should use `label-caps` typography for the title.