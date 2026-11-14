# Map image provenance

`public/assets/ranch-aerial.png` was generated with the built-in image-generation tool for this project, then copied into the workspace. It is a fictional aerial landscape, not real ranch imagery or a georeferenced map. UI boundaries, labels and animal markers are independent SVG/HTML elements.

Exact generation prompt:

> Use case: photorealistic-natural. Asset type: full-bleed aerial map background for a cattle monitoring dashboard. Generate only an orthographic satellite/drone-like photograph of rural California cattle ranch terrain viewed straight down: muted olive-green and golden dry grassland, scattered round oak trees casting short shadows, winding light dirt tracks, two broad central open pastures in the upper and lower halves, small dark pond near bottom left. Fine realistic satellite texture, natural understated colors, flat evenly lit top-down view, no horizon. Near square portrait aspect ratio. Absolutely no text, labels, map markers, boundaries, UI, buildings in central pastures, icons, diagrams, borders, logos or watermarks. This is an illustrative fictional ranch, not a georeferenced real location.

The supplied `webapp.png` was used as the interface layout/design reference. Cow marks/favicon are code-native SVG; UI icons use the starter's Lucide React package. No external map provider or real location service is called.

## Spotlight placeholder

`public/assets/cow-illustration.png` was generated with the built-in image tool, copied into this project, and is labeled **Illustrative preview** in every card using it. It is a shared generic placeholder, not evidence or a distinct animal identity. The viewer replaces it with a thumbnail extracted from an attached clip.

Exact prompt:

> Photorealistic editorial ranch photograph for an explicitly illustrative cow-monitoring demo card. A healthy adult black-and-white Holstein cow seen from a slightly elevated drone viewpoint, full body clearly visible, standing in muted olive green pasture, soft late-afternoon light, realistic natural fur and grass texture. Subtle out-of-focus distant oak trees, calm natural scene, subject centered, lots of grass around its head and shoulders for a circular crop. No visible readable ear tag, no numbers, no text, no labels, no graphic overlays, no interface, no logos, no watermark. Landscape 4:3 composition. This is generic illustrative cattle imagery, not evidence for a specific animal.

For decoder/playback QA only, MDN's public CC0 flower video was downloaded into ignored `outputs/test-media/decoder-test.mp4`. It is not shipped as cow footage or included in the deployment. Its temporary browser attachment was removed after testing.
