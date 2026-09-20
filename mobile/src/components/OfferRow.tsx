/**
 * Karta oferty na ekranie Magazyn — miniatura, tytuł, kanał sprzedaży
 * i cena. Cztery rzeczy, po których poznaje się własny asortyment
 * bez wchodzenia w szczegóły.
 *
 * Kanał jest pastylką w kolorze z `marketplaceColor` - tej samej, którą
 * ORDLY oznacza zamówienia i maile, więc „pomarańczowe = Allegro” znaczy
 * na każdym ekranie to samo.
 */
import * as React from "react";
import { Image, StyleSheet, Text, View } from "react-native";

import { CHANNEL_LABEL, channelDay, channelNight } from "@/theme/colors";
import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { radii, spacing, typography } from "@/theme/typography";
import { BoxIcon } from "@/icons";
import { formatMoney } from "@/utils/format";
import type { MarketplaceOffer } from "@/api/types";





export function OfferRow({ offer }: { offer: MarketplaceOffer }) {
  const styles = useThemedStyles(createStyles);
  const { c, mode } = useTheme();
  const palette = mode === "day" ? channelDay : channelNight;
  const channel = palette[offer.marketplace] ?? { background: c.card2, text: c.tx2 };
  const label = CHANNEL_LABEL[offer.marketplace] ?? offer.marketplace;

  return (
    <View style={styles.card}>
      {offer.image_url ? (
        <Image source={{ uri: offer.image_url }} style={styles.thumb} resizeMode="cover" />
      ) : (
        <View style={[styles.thumb, styles.thumbEmpty]}>
          <BoxIcon size={20} color={c.tx3} />
        </View>
      )}

      <View style={styles.info}>
        <Text style={styles.name} numberOfLines={2}>
          {offer.name}
        </Text>
        <View style={styles.meta}>
          <View style={[styles.channel, { backgroundColor: channel.background }]}>
            <Text style={[styles.channelLabel, { color: channel.text }]} numberOfLines={1}>
              {label}
            </Text>
          </View>
          {/* Oferta bez ceny to na Allegro wariant z cennikiem - kreska
              mówi „tu nie ma jednej kwoty”, a nie „0 zł”. */}
          <Text style={styles.price}>
            {offer.price === null ? "—" : formatMoney(offer.price)}
          </Text>
        </View>
      </View>
    </View>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: c.card,
    borderWidth: 1,
    borderColor: c.line,
    borderRadius: radii.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  thumb: {
    width: 56,
    height: 56,
    borderRadius: radii.md,
    backgroundColor: c.card2,
  },
  thumbEmpty: {
    alignItems: "center",
    justifyContent: "center",
  },
  info: {
    flex: 1,
    minWidth: 0,
    gap: 6,
  },
  name: {
    ...typography.calloutSemibold,
    color: c.tx,
  },
  meta: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: spacing.sm,
  },
  channel: {
    height: 20,
    borderRadius: radii.full,
    paddingHorizontal: 8,
    justifyContent: "center",
    flexShrink: 1,
  },
  channelLabel: {
    ...typography.badgeLabel,
  },
  price: {
    // Cyfry tabelaryczne: ceny stoją jedna pod drugą w kolumnie, więc
    // przecinki mają się zgadzać przy przewijaniu listy.
    ...typography.statValue,
    fontSize: 15,
    lineHeight: 20,
    color: c.tx,
  },
});
