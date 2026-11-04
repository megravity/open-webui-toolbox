# Open WebUI model icon family

**Version 1.0** · A visual specification for consistent Open WebUI agent icons.

The defining style is monochromatic, softly geometric, high-contrast, and minimally dimensional, with a consistent dark background and prominent ivory pictograms. The icons should resemble a coherent desktop application icon family.

## References

| Chat | Task Master | Instance Assistant |
| --- | --- | --- |
| ![Chat icon](references/chat.png) | ![Task Master icon](references/task-master.png) | ![Instance Assistant icon](references/instance-assistant.png) |

The reference PNGs are preserved at their supplied 1254 × 1254 resolution. Match their background treatment, proportions, palette, and visual weight when creating new icons.

## Palette and surface

| Role | Approximate color | Use |
| --- | --- | --- |
| Outer canvas | `#000000` | Black area outside the rounded square |
| Icon background | `#101116` | Near-black charcoal with a faint cool undertone |
| Primary foreground | `#F3F2F3` | Soft ivory-white for dominant symbols |
| Secondary foreground | `#C7C7CB` | Light neutral gray for supporting elements |

These are approximate reference colors, not exact sampled pixel values. Foreground shapes have subtle tonal variation for a softer finish than purely flat SVG icons. Keep shading nearly imperceptible; avoid noticeable gradients, shadows, glows, bevels, or material effects.

## Geometry and composition

| Property | Specification |
| --- | --- |
| Canvas | Square, 1:1 |
| Recommended resolution for new icons | 1024 × 1024 px |
| Background | Large rounded square |
| Background corner radius | Approximately 20–23% |
| Symbol coverage | Approximately 60–70% of canvas width |
| Outer margin | Approximately 10–15% |
| Stroke treatment | Heavy, rounded, consistent |
| Shape treatment | Solid fills and thick outlines |
| Alignment | Optically centered |
| Typography | None |

Give the pictogram a strong, recognizable silhouette and keep internal details legible at small avatar sizes. Match optical weight rather than enforcing identical symbol dimensions.

## Reference compositions

- **Task Master:** A vertically oriented clipboard with a solid top clip. Three task rows, two completed and one unchecked. Rounded horizontal lines, subtle tonal variation, and an approximately symmetrical composition.
- **Instance Assistant:** A browser window with three circular controls, a gray divider, and code brackets. A solid gear overlaps the lower-right corner, adding asymmetry and depth without 3D effects.
- **Chat:** Two overlapping speech bubbles. The foreground bubble is filled ivory-white with three dark dots; the rear bubble uses a thick open outline. Strong figure-ground contrast and minimal internal detail.

## Family rules

- Preserve identical background shape, positioning, and surface treatment.
- Use one recognizable central metaphor per agent. Overlapping secondary shapes are welcome when they improve recognition.
- Favor bold outlines, solid forms, and rounded geometry. Use limited gray accents for secondary information.
- Avoid text, bright colors, decorative sparkles, robot faces, complex scenes, and unnecessary ornamentation.
- For maximum consistency, use an existing reference as the starting point and replace only the foreground pictogram rather than independently regenerating the entire composition.

## Creation prompt

Fill in the bracketed fields and provide the reference images with the prompt:

> Create a square application icon for **[AGENT NAME]**, representing **[AGENT FUNCTION]**.
>
> Use the supplied reference icons as a strict visual style guide. Match their visual identity:
>
> - Square black canvas with a large, near-black, subtly blue-tinted rounded-square background.
> - Soft ivory-white central pictogram with limited light-gray accents.
> - Bold geometric shapes, thick rounded outlines, and smooth corners.
> - Large, optically centered symbol with generous negative space.
> - Subtle tonal variation in the foreground, without obvious gradients or dimensional effects.
> - Clear visual hierarchy and strong recognition at small sizes.
> - Consistent background proportions, corner radius, stroke weight, and overall visual density.
>
> Use one primary visual metaphor. Secondary overlapping elements are permitted when they add meaning.
>
> Avoid text, bright colors, decorative details, glows, strong shadows, 3D rendering, and generic AI imagery.
>
> Icon concept: **[DESCRIBE PRIMARY SYMBOL AND COMPOSITION]**
>
> Match the reference images as closely as possible. Change the pictogram, not the established visual language.

## Acceptance check

A new icon belongs to this family when its background matches the references, its foreground maintains consistent visual weight and color treatment, its symbol remains recognizable at small sizes, and it introduces no conflicting stylistic elements.
