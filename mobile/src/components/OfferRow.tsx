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

import { colors, marketplaceColor } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";
import { BoxIcon } from "@/icons";
import { formatMoney } from "@/utils/format";
import type { MarketplaceOffer } from "@/api/types";

const MARKETPLACE_LABEL: Record<string, string> = {
  allegro: "Allegro",
  allegro_lokalnie: "Allegro Lokalnie",
  olx: "OLX",
  amazon: "Amazon",
  ebay: "eBay",
};

const NEUTRAL_CHANNEL = { background: colors.surfaceRaised, text: colors.textSecondary };

export function OfferRow({ offer }: { offer: MarketplaceOffer }) {
  const channel = marketplaceColor[offer.marketplace] ?? NEUTRAL_CHANNEL;
  const label = MARKETPLACE_LABEL[offer.marketplace] ?? offer.marketplace;

  return (
    <View style={styles.card}>
      {offer.image_url ? (
        <Image source={{ uri: offer.image_url }} style={styles.thumb} resizeMode="cover" />
      ) : (
        <View style={[styles.thumb, styles.thumbEmpty]}>
          <BoxIcon size={20} color={colors.textDim} />
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

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  thumb: {
    width: 56,
    height: 56,
    borderRadius: radii.md,
    backgroundColor: colors.surfaceRaised,
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
    color: colors.text,
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
    color: colors.text,
  },
});
