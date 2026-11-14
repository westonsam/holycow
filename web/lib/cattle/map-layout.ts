// Normalized fictional viewport coordinates, not geographic coordinates.
export const PASTURES: Record<string, [number, number][]> = {
  "herd-1": [
    [27, 23.5],
    [42, 17],
    [51.5, 7],
    [56.5, 8.3],
    [59.5, 13],
    [61, 23],
    [69, 37.5],
    [38.5, 44.5],
    [35, 35],
  ],
  "herd-2": [
    [18, 59.5],
    [26, 57],
    [28.5, 62.5],
    [37.5, 61],
    [39, 55],
    [47, 49],
    [49, 52.5],
    [63, 52],
    [66.5, 57],
    [72.5, 65],
    [80, 82.5],
    [44.5, 91],
    [39, 78.5],
    [29, 77.5],
    [23.5, 80.5],
  ],
};
export const svgPoints = (herd: string) =>
  PASTURES[herd].map(([x, y]) => `${x * 10},${y * 10}`).join(" ");
export function inPasture(x: number, y: number, herd: string) {
  const points = PASTURES[herd];
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const [xi, yi] = points[i],
      [xj, yj] = points[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi)
      inside = !inside;
  }
  return inside;
}
export function demoPosition(index: number, herd: string) {
  let seed = (index + 1) * 7919 + (herd === "herd-1" ? 31 : 417);
  const random = () => {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  };
  for (let attempt = 0; attempt < 1000; attempt++) {
    const x = 20 + random() * 58,
      y = herd === "herd-1" ? 10 + random() * 31 : 54 + random() * 31;
    const label =
      herd === "herd-1"
        ? y > 25 && y < 31 && x > 44 && x < 57
        : y > 70 && y < 76 && x > 45 && x < 58;
    if (inPasture(x, y, herd) && !label) return { x, y };
  }
  return { x: 50, y: herd === "herd-1" ? 20 : 65 };
}
