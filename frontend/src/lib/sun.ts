// Sunrise/sunset from the standard sunrise equation (NOAA-style, about +-2 min at low latitudes).
// Inputs: any instant on the wanted local day (local noon is best), site latitude/longitude in degrees.
const RAD = Math.PI / 180
const DAY = 86400e3
const J1970 = 2440587.5
const J2000 = 2451545

export function sunTimes(ms: number, lat: number, lon: number): { rise: number; set: number } {
  const n = Math.round(ms / DAY + J1970 - J2000 + 0.0008)
  const jStar = n - lon / 360
  const M = ((357.5291 + 0.98560028 * jStar) % 360) * RAD
  const C = 1.9148 * Math.sin(M) + 0.02 * Math.sin(2 * M) + 0.0003 * Math.sin(3 * M)
  const lambda = ((M / RAD + C + 180 + 102.9372) % 360) * RAD
  const transit = J2000 + jStar + 0.0053 * Math.sin(M) - 0.0069 * Math.sin(2 * lambda)
  const sinDec = Math.sin(lambda) * Math.sin(23.4397 * RAD)
  const cosDec = Math.cos(Math.asin(sinDec))
  const cosW = (Math.sin(-0.833 * RAD) - Math.sin(lat * RAD) * sinDec) / (Math.cos(lat * RAD) * cosDec)
  // shortcut: clamps polar day/night to a full or empty day; irrelevant for the tropics.
  const w = Math.acos(Math.max(-1, Math.min(1, cosW))) / RAD
  const toMs = (j: number) => (j - J1970) * DAY
  return { rise: toMs(transit - w / 360), set: toMs(transit + w / 360) }
}

/** Position of the sun along today's arc: 0 at sunrise, 1 at sunset, null when the sun is down. */
export function sunFraction(now: number, rise: number, set: number): number | null {
  if (now < rise || now > set) return null
  return (now - rise) / (set - rise)
}
