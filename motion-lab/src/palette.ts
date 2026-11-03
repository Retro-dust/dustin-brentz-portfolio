import type { PaletteId } from "./data";

export function readPalette(): PaletteId {
  const params = new URLSearchParams(window.location.search);
  const value = (params.get("palette") ?? params.get("p") ?? "a").toLowerCase();
  return value === "e" ? "e" : "a";
}

export function writePalette(next: PaletteId) {
  const url = new URL(window.location.href);
  if (next === "a") {
    url.searchParams.delete("palette");
    url.searchParams.delete("p");
  } else {
    url.searchParams.set("palette", "e");
    url.searchParams.delete("p");
  }
  const hash = window.location.hash;
  window.history.replaceState({}, "", `${url.pathname}${url.search}${hash}`);
}
