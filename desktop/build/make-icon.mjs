/**
 * Ikony ORDLY - JEDNO zrodlo dla wszystkich platform (styl "Nokturn").
 *
 *   node build/make-icon.mjs            -> zapisuje do repozytorium
 *   node build/make-icon.mjs --out DIR  -> zapisuje do DIR (podglad przed akceptacja)
 *
 * Tworzy:
 *   desktop/build/icon.ico            8 rozmiarow (16-256) - .exe, pasek zadan
 *   desktop/build/icon.png            256 px
 *   desktop/build/icon.svg, icon-small.svg
 *   mobile/assets/icon.png            1024 px, BEZ kanalu alfa (App Store)
 *   mobile/assets/icon.svg
 *   mobile/public/icon.png            1024 px - ikona powiadomien push
 *   mobile/public/apple-touch-icon.png 180 px - ekran glowny iPhone'a
 *   mobile/public/icon-192.png, icon-512.png - manifest PWA
 *   backend/docs/assets/ordly-icon-120.png - podglad powiadomien
 *
 * SYMETRIA. Ikona pokazuje Ordlaka NA WPROST, bez notatnika, wysrodkowanego
 * na osi twarzy (x = 60). Pierwsza wersja centrowala cala sylwetke razem
 * z notatnikiem - notatnik ciagnal ja w prawo, a twarz, na ktora patrzy oko,
 * ladowala 12,4 jednostki na lewo od srodka (w dymku powiadomienia ~3 px,
 * dobrze widoczne). Stopy sa tu tez przesuniete na os symetrii: w komponencie
 * aplikacji maja os x = 58, nie 60.
 *
 * Male rozmiary (16-32 px) maja osobny, uproszczony rysunek: instrukcja
 * Nokturn mowi, ze "ponizej 22 px Ordlak traci oczy".
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync, crc32 } from "node:zlib";
import { Resvg } from "@resvg/resvg-js";

const here = dirname(fileURLToPath(import.meta.url));
const outArg = process.argv.indexOf("--out");
const ROOT = outArg > 0 ? resolve(process.argv[outArg + 1]) : resolve(here, "..", "..");

const TEAL = "#5FD9CC";
const TEAL_2 = "#3EAAAF";
const EYE = "#062120";

// --------------------------------------------------------------- tlo

/** Gradienty tla: petrol z JEDNYM zrodlem swiatla u gory po lewej (zasada 1). */
function backgroundDefs() {
  return `
    <linearGradient id="base" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#0E1C1A"/><stop offset="1" stop-color="#0A1615"/>
    </linearGradient>
    <radialGradient id="key" cx="0.16" cy="-0.06" r="0.95">
      <stop offset="0" stop-color="#1F7D80" stop-opacity=".72"/>
      <stop offset=".62" stop-color="#1F7D80" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="halo" cx="0.5" cy="0.54" r="0.38">
      <stop offset="0" stop-color="${TEAL}" stop-opacity=".2"/>
      <stop offset="1" stop-color="${TEAL}" stop-opacity="0"/>
    </radialGradient>`;
}

function fill(x, y, w) {
  return `
    <rect x="${x}" y="${y}" width="${w}" height="${w}" fill="url(#base)"/>
    <rect x="${x}" y="${y}" width="${w}" height="${w}" fill="url(#key)"/>
    <rect x="${x}" y="${y}" width="${w}" height="${w}" fill="url(#halo)"/>`;
}

// ----------------------------------------------------------- maskotka

/**
 * Ordlak na wprost (stan idle), symetryczny wzgledem x = 60.
 * (60, 66) to srodek postaci - ramki od anteny (y 16) po stopy i cien.
 */
function mascot({ cx, cy, k }) {
  return `
  <g transform="translate(${cx} ${cy}) scale(${k}) translate(-60 -66)">
    <ellipse cx="60" cy="118" rx="29" ry="4.6" fill="#000" opacity=".38"/>
    <rect x="38" y="101" width="16" height="12" rx="6" fill="${TEAL_2}"/>
    <rect x="66" y="101" width="16" height="12" rx="6" fill="${TEAL_2}"/>
    <line x1="60" y1="46" x2="60" y2="27" stroke="${TEAL_2}" stroke-width="3.4" stroke-linecap="round"/>
    <circle cx="60" cy="22" r="6" fill="${TEAL}"/>
    <rect x="26" y="44" width="68" height="64" rx="28" fill="${TEAL}"/>
    <ellipse cx="48" cy="70" rx="6" ry="7" fill="${EYE}"/>
    <ellipse cx="72" cy="70" rx="6" ry="7" fill="${EYE}"/>
    <circle cx="50.2" cy="66.8" r="2" fill="#EAF3EF" opacity=".92"/>
    <circle cx="74.2" cy="66.8" r="2" fill="#EAF3EF" opacity=".92"/>
    <path d="M52 86q8 6 16 0" stroke="${EYE}" stroke-width="3.4" stroke-linecap="round" fill="none"/>
  </g>`;
}

/** Maly Ordlak (16-32 px): cialo, antena, dwoje duzych oczu. Symetryczny wzgledem x = 60. */
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

const svg = (size, body) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">${body}</svg>`;

// -------------------------------------------------------------- rysunki

/** iOS / PWA: pelny kwadrat, bez zaokraglen - maske naklada system. */
const IOS = svg(
  1024,
  `<defs>${backgroundDefs()}</defs>${fill(0, 0, 1024)}${mascot({ cx: 512, cy: 512, k: 6.6 })}`
);

/** Windows: wlasny kafelek, przezroczyste rogi, cienka jasna krawedz. */
const DESKTOP = svg(
  256,
  `<defs>${backgroundDefs()}<clipPath id="kafel"><rect x="12" y="12" width="232" height="232" rx="52"/></clipPath></defs>
   <g clip-path="url(#kafel)">${fill(12, 12, 232)}</g>
   <rect x="13.5" y="13.5" width="229" height="229" rx="50.5" fill="none" stroke="rgba(214,235,228,.16)" stroke-width="3"/>
   ${mascot({ cx: 128, cy: 128, k: 1.5 })}`
);

/** Windows 16-32 px: kafelek wypelnia cale pole, bo przy 16 px margines to strata piksela. */
const DESKTOP_SMALL = svg(
  256,
  `<defs>${backgroundDefs()}<clipPath id="kafel"><rect width="256" height="256" rx="48"/></clipPath></defs>
   <g clip-path="url(#kafel)">${fill(0, 0, 256)}</g>
   ${smallMascot({ cx: 128, cy: 132, k: 2.0 })}`
);

// ------------------------------------------------------------- zapis

function out(rel, data) {
  const path = join(ROOT, rel);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, data);
}

const rgba = (source, size) => new Resvg(source, { fitTo: { mode: "width", value: size } }).render();

/**
 * PNG bez kanalu alfa (typ koloru 2 = RGB). Apple odrzuca ikony
 * z przezroczystoscia, a resvg zawsze zapisuje RGBA - wiec kodujemy sami.
 */
function pngRgb(source, size) {
  const img = rgba(source, size);
  const { width, height } = img;
  const px = img.pixels;
  const stride = width * 3 + 1;
  const raw = Buffer.alloc(stride * height);
  for (let y = 0; y < height; y++) {
    raw[y * stride] = 0; // filtr: brak
    for (let x = 0; x < width; x++) {
      const s = (y * width + x) * 4;
      const d = y * stride + 1 + x * 3;
      raw[d] = px[s];
      raw[d + 1] = px[s + 1];
      raw[d + 2] = px[s + 2];
    }
  }
  const chunk = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(body) >>> 0);
    return Buffer.concat([len, body, crc]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bity na kanal
  ihdr[9] = 2; // RGB
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

// iPhone / PWA / podglad powiadomien
out("mobile/assets/icon.svg", IOS);
out("mobile/assets/icon.png", pngRgb(IOS, 1024));
out("mobile/public/icon.png", pngRgb(IOS, 1024));
out("mobile/public/apple-touch-icon.png", pngRgb(IOS, 180));
out("mobile/public/icon-192.png", pngRgb(IOS, 192));
out("mobile/public/icon-512.png", pngRgb(IOS, 512));
out("backend/docs/assets/ordly-icon-120.png", pngRgb(IOS, 120));

// Windows
out("desktop/build/icon.svg", DESKTOP);
out("desktop/build/icon-small.svg", DESKTOP_SMALL);
out("desktop/build/icon.png", rgba(DESKTOP, 256).asPng());

// Rozmiary, ktorych Windows uzywa przy roznym DPI. 16-32 px dostaja maly
// rysunek - pelny mial przy 32 px oczy po ~2 piksele.
const SIZES = [16, 20, 24, 32, 40, 48, 64, 256];
const images = SIZES.map((size) => ({
  size,
  png: rgba(size <= 32 ? DESKTOP_SMALL : DESKTOP, size).asPng(),
}));
const header = Buffer.alloc(6 + 16 * images.length);
header.writeUInt16LE(0, 0); // zarezerwowane
header.writeUInt16LE(1, 2); // typ: ikona
header.writeUInt16LE(images.length, 4);
let offset = header.length;
images.forEach(({ size, png }, i) => {
  const at = 6 + i * 16;
  header.writeUInt8(size >= 256 ? 0 : size, at); // 0 znaczy 256
  header.writeUInt8(size >= 256 ? 0 : size, at + 1);
  header.writeUInt16LE(1, at + 4); // plaszczyzny
  header.writeUInt16LE(32, at + 6); // bity na piksel
  header.writeUInt32LE(png.length, at + 8);
  header.writeUInt32LE(offset, at + 12);
  offset += png.length;
});
out("desktop/build/icon.ico", Buffer.concat([header, ...images.map((i) => i.png)]));

console.log(`Zapisano ikony do ${ROOT}`);
