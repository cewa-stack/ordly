/**
 * Ikona aplikacji desktopowej ORDLY (Windows) - styl "Nokturn".
 *
 *   node build/make-icon.mjs
 *
 * Sklada `build/icon.ico` (8 rozmiarow) i `build/icon.png` (256 px) z dwoch
 * rysunkow, ktore zapisuje obok jako zrodla:
 *
 *   icon.svg        - pelny Ordlak z notatnikiem, dla 40 px i wiekszych
 *   icon-small.svg  - uproszczony Ordlak dla 16/20/24/32 px
 *
 * Dlaczego dwa rysunki: instrukcja Nokturn mowi wprost, ze "ponizej 22 px
 * Ordlak traci oczy". Pomniejszony pelny rysunek robi sie przy 16 px
 * turkusowa plama z notatnikiem. Maly wariant nie ma notatnika, cienia ani
 * odblaskow - ma cialo, antene i dwoje wyraznych oczu, powiekszone tak,
 * zeby wypelnialy kafelek.
 *
 * Roznica wobec ikony iOS (`mobile/assets/icon.svg`): Windows NIE naklada
 * maski, wiec kafelek ma wlasne zaokraglenie i przezroczyste rogi. Ma tez
 * cienka jasna krawedz - bez niej ciemny kafelek znikal na ciemnym pasku
 * zadan.
 *
 * Geometria maskotki jest 1:1 z `src/renderer/src/components/Ordlak.tsx`.
 */
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Resvg } from "@resvg/resvg-js";

const here = dirname(fileURLToPath(import.meta.url));

const TEAL = "#5FD9CC";
const TEAL_2 = "#3EAAAF";
const EYE = "#062120";

/** Kafelek: petrol z jednym zrodlem swiatla u gory po lewej (zasada 1). */
function tile({ size, inset, radius, edge }) {
  const w = size - inset * 2;
  return `
  <defs>
    <linearGradient id="base" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0E1C1A"/><stop offset="1" stop-color="#0A1615"/>
    </linearGradient>
    <radialGradient id="key" cx="0.16" cy="-0.06" r="0.95">
      <stop offset="0" stop-color="#1F7D80" stop-opacity=".72"/>
      <stop offset=".62" stop-color="#1F7D80" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="halo" cx="0.47" cy="0.52" r="0.38">
      <stop offset="0" stop-color="${TEAL}" stop-opacity=".2"/>
      <stop offset="1" stop-color="${TEAL}" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="kafel"><rect x="${inset}" y="${inset}" width="${w}" height="${w}" rx="${radius}"/></clipPath>
  </defs>
  <g clip-path="url(#kafel)">
    <rect x="${inset}" y="${inset}" width="${w}" height="${w}" fill="url(#base)"/>
    <rect x="${inset}" y="${inset}" width="${w}" height="${w}" fill="url(#key)"/>
    <rect x="${inset}" y="${inset}" width="${w}" height="${w}" fill="url(#halo)"/>
  </g>
  ${
    edge
      ? `<rect x="${inset + edge / 2}" y="${inset + edge / 2}" width="${w - edge}" height="${w - edge}"
          rx="${radius - edge / 2}" fill="none" stroke="rgba(214,235,228,.16)" stroke-width="${edge}"/>`
      : ""
  }`;
}

/** Pelny Ordlak (stan idle) - z notatnikiem i cieniem. */
function fullMascot({ cx, cy, k }) {
  return `
  <g transform="translate(${cx} ${cy}) scale(${k}) translate(-72.4 -67)">
    <ellipse cx="60" cy="118" rx="29" ry="4.6" fill="#000" opacity=".38"/>
    <rect x="36" y="101" width="16" height="12" rx="6" fill="${TEAL_2}"/>
    <rect x="64" y="101" width="16" height="12" rx="6" fill="${TEAL_2}"/>
    <line x1="60" y1="46" x2="60" y2="27" stroke="${TEAL_2}" stroke-width="3.4" stroke-linecap="round"/>
    <circle cx="60" cy="22" r="6" fill="${TEAL}"/>
    <rect x="26" y="44" width="68" height="64" rx="28" fill="${TEAL}"/>
    <ellipse cx="48" cy="70" rx="6" ry="7" fill="${EYE}"/>
    <ellipse cx="72" cy="70" rx="6" ry="7" fill="${EYE}"/>
    <circle cx="50.2" cy="66.8" r="2" fill="#EAF3EF" opacity=".92"/>
    <circle cx="74.2" cy="66.8" r="2" fill="#EAF3EF" opacity=".92"/>
    <path d="M52 86q8 6 16 0" stroke="${EYE}" stroke-width="3.4" stroke-linecap="round" fill="none"/>
    <g transform="rotate(7 101 81)">
      <rect x="86" y="62" width="30" height="38" rx="5" fill="#0B1A18" stroke="${TEAL_2}" stroke-width="2.6"/>
      <rect x="95" y="57" width="12" height="8" rx="3" fill="${TEAL_2}"/>
      <line x1="92" y1="76" x2="110" y2="76" stroke="${TEAL}" stroke-width="2.6" stroke-linecap="round" opacity=".5"/>
      <line x1="92" y1="84" x2="110" y2="84" stroke="${TEAL}" stroke-width="2.6" stroke-linecap="round" opacity=".5"/>
      <line x1="92" y1="92" x2="104" y2="92" stroke="${TEAL}" stroke-width="2.6" stroke-linecap="round" opacity=".5"/>
    </g>
  </g>`;
}

/**
 * Maly Ordlak (16-32 px): cialo, antena, dwoje oczu. Oczy sa wieksze niz
 * w pelnym rysunku - przy 16 px pelne oko ma ponizej piksela i znika.
 */
function smallMascot({ cx, cy, k }) {
  return `
  <g transform="translate(${cx} ${cy}) scale(${k}) translate(-60 -66)">
    <line x1="60" y1="46" x2="60" y2="24" stroke="${TEAL_2}" stroke-width="6" stroke-linecap="round"/>
    <circle cx="60" cy="21" r="9" fill="${TEAL}"/>
    <rect x="22" y="42" width="76" height="70" rx="30" fill="${TEAL}"/>
    <ellipse cx="45" cy="74" rx="9.5" ry="11" fill="${EYE}"/>
    <ellipse cx="75" cy="74" rx="9.5" ry="11" fill="${EYE}"/>
  </g>`;
}

function svg(size, body) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${body}</svg>`;
}

// Rysunki w siatce 256 px - z nich renderuje sie kazdy rozmiar.
const S = 256;
const fullSvg = svg(
  S,
  tile({ size: S, inset: 12, radius: 52, edge: 3 }) + fullMascot({ cx: 128, cy: 130, k: 1.58 })
);
const smallSvg = svg(
  S,
  // Przy 16 px margines kafelka to strata piksela - kafelek wypelnia cale pole.
  tile({ size: S, inset: 0, radius: 48, edge: 0 }) + smallMascot({ cx: 128, cy: 134, k: 2.0 })
);

writeFileSync(join(here, "icon.svg"), fullSvg);
writeFileSync(join(here, "icon-small.svg"), smallSvg);

function render(source, size) {
  return new Resvg(source, { fitTo: { mode: "width", value: size } }).render().asPng();
}

// Rozmiary, ktorych Windows uzywa przy roznym DPI: pasek zadan, Eksplorator,
// pulpit, Alt+Tab. Te same osiem, co w poprzedniej ikonie.
const SIZES = [16, 20, 24, 32, 40, 48, 64, 256];
const images = SIZES.map((size) => ({
  size,
  // 32 px tez dostaje maly rysunek: pelny mial tam oczy po ~2 piksele,
  // a to rozmiar paska zadan przy skalowaniu 125-150%.
  png: render(size <= 32 ? smallSvg : fullSvg, size),
}));

// Kontener ICO z wpisami PNG (Windows Vista i nowsze).
const header = Buffer.alloc(6 + 16 * images.length);
header.writeUInt16LE(0, 0); // zarezerwowane
header.writeUInt16LE(1, 2); // typ: ikona
header.writeUInt16LE(images.length, 4);
let offset = header.length;
images.forEach(({ size, png }, i) => {
  const at = 6 + i * 16;
  header.writeUInt8(size >= 256 ? 0 : size, at); // 0 znaczy 256
  header.writeUInt8(size >= 256 ? 0 : size, at + 1);
  header.writeUInt8(0, at + 2); // paleta
  header.writeUInt8(0, at + 3);
  header.writeUInt16LE(1, at + 4); // plaszczyzny
  header.writeUInt16LE(32, at + 6); // bity na piksel
  header.writeUInt32LE(png.length, at + 8);
  header.writeUInt32LE(offset, at + 12);
  offset += png.length;
});

writeFileSync(join(here, "icon.ico"), Buffer.concat([header, ...images.map((i) => i.png)]));
writeFileSync(join(here, "icon.png"), render(fullSvg, 256));
console.log(`Zapisano icon.ico (${SIZES.join("/")} px) i icon.png`);
