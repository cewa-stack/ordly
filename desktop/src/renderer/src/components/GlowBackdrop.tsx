/**
 * Miekka poswiata za maskotka - musi byc renderowana wewnatrz wrappera,
 * ktory otacza WYLACZNIE obrazek maskotki (patrz LoginScreen.tsx), bo
 * centruje sie wzgledem bezposredniego rodzica. Centrowanie wzgledem
 * calego, wyzej wyśrodkowanego flexboksem ekranu logowania rozjezdza
 * sie od faktycznej pozycji maskotki przy realnej wysokosci okna.
 * Radial-gradient (nie plaska przezroczystosc jak w mobile/GlowBackdrop.tsx)
 * zanika plynnie zamiast urywac sie twardym brzegiem kola.
 */
export function GlowBackdrop() {
  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden="true">
      <div
        className="absolute left-1/2 top-1/2 rounded-full"
        style={{
          width: 280,
          height: 280,
          marginLeft: -140,
          marginTop: -140,
          background:
            "radial-gradient(circle, rgba(86,224,208,0.16) 0%, rgba(86,224,208,0.07) 45%, rgba(86,224,208,0) 75%)",
        }}
      />
      <div
        className="absolute left-1/2 top-1/2 rounded-full"
        style={{
          width: 190,
          height: 190,
          marginLeft: -95,
          marginTop: -95,
          background:
            "radial-gradient(circle, rgba(86,224,208,0.22) 0%, rgba(86,224,208,0.09) 45%, rgba(86,224,208,0) 75%)",
        }}
      />
      <div
        className="absolute left-1/2 top-1/2 rounded-full"
        style={{
          width: 120,
          height: 120,
          marginLeft: -60,
          marginTop: -60,
          background:
            "radial-gradient(circle, rgba(86,224,208,0.3) 0%, rgba(86,224,208,0.12) 45%, rgba(86,224,208,0) 75%)",
        }}
      />
    </div>
  );
}
