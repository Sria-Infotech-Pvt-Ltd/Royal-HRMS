const clean = (text: string) => text.trim().replace(/\s+/g, " ").toLowerCase();

/** The listed spelling of a place name, matched ignoring case and extra spaces ("TELANGANA" gives "Telangana"), or null. */
export function canonicalName(options: string[], name: string): string | null {
  const wanted = clean(name);
  return wanted ? options.find(option => clean(option) === wanted) ?? null : null;
}
