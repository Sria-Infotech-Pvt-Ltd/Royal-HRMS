// The words on the Add / Edit Company Code form, in one place: a plain heading and one sentence of help for each part.

export const SECTION_COPY = {
  location: { title: "Where is it?", hint: "Choose the state and city. The Company Code is made from the city for you." },
  details: { title: "Name and address", hint: "What people will see for this office." },
  settings: { title: "Office settings", hint: "Whether it is in use, and whether it is a special office." },
  admin: { title: "Company Code Admin", hint: "Pick the person who looks after this office. You can skip this and add them later." },
  geofence: { title: "Attendance area (geofence)", hint: "Turn this on to allow punching in only near the office. Leave it off to allow punching in from anywhere." },
} as const;

export const RADIUS_PRESETS = [50, 100, 150, 250, 500] as const;
export const RADIUS_MIN = 10;
export const RADIUS_MAX = 5000;
/** The slider covers the useful range; the number box still accepts anything up to RADIUS_MAX. */
export const RADIUS_SLIDER_MAX = 1000;

/** The geofence part's folded summary: "Off: people can punch in from anywhere" or "On: within 150 m of the office". */
export function geofenceSummary(enabled: boolean, radius: string): string {
  return enabled ? `On: within ${radius.trim() || "?"} m of the office` : "Off: people can punch in from anywhere";
}
