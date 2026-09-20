/**
 * Wiersz zamówienia (sekcja 12 instrukcji "Nokturn").
 *
 *   etykieta kanału (STAŁE 60 px, wyśrodkowana)
 *   nazwisko 13,5/600 z ucięciem · pod nim numer i godzina 11,5 px
 *   po prawej: kwota mono 13/600 · pod nią status 10,5/600
 *
 * Stała szerokość etykiety kanału jest OBOWIĄZKOWA. Bez niej "Lokalnie"
 * jest szersze od "OLX" i nazwiska zaczynają się w różnych miejscach -
 * to był najbardziej widoczny błąd pierwszej wersji.
 *
 * Nazwisko i podwiersz są ucinane, więc KAŻDY wiersz ma tę samą
 * wysokość niezależnie od długości nazwy kupującego.
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import {
  CHANNEL_LABEL,
  ORDER_TONE,
  channelDay,
  channelNight,
  toneStyle,
} from "@/theme/colors";
import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { fonts, radii } from "@/theme/typography";
import type { Order } from "@/api/types";
import { displayFulfillmentLabel, formatMoney, parseApiDate } from "@/utils/format";

interface OrderRowProps {
  order: Order;
  onPress?: () => void;
}

/**
 * Podwiersz niesie NUMER I GODZINE (sekcja 12), a date tylko wtedy, gdy
 * zamowienie nie jest z dzisiaj. Pelna data przy kazdej pozycji nie
 * miescila sie w kolumnie i ucinala sie wielokropkiem, wiec godzina -
 * jedyna rzecz, ktora naprawde rozroznia dzisiejsze zamowienia - znikala.
 */
function shortStamp(iso: string): string {
  const date = parseApiDate(iso);
  const time = date.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
  if (date.toDateString() === new Date().toDateString()) return time;
  return `${date.toLocaleDateString("pl-PL", { day: "numeric", month: "short" })} ${time}`;
}

export function OrderRow({ order, onPress }: OrderRowProps) {
  const styles = useThemedStyles(createStyles);
  const { c, mode } = useTheme();

  const label = displayFulfillmentLabel(order);
  const tone = toneStyle(ORDER_TONE[label] ?? "mute", c);
  const channelPalette = mode === "day" ? channelDay : channelNight;
  const channel = channelPalette[order.marketplace] ?? {
    background: c.card2,
    text: c.tx3,
  };
  // Surowy kod kanału ("allegro_lokalnie") nie jest nazwą dla człowieka.
  const channelLabel = CHANNEL_LABEL[order.marketplace] ?? order.marketplace;

  return (
    <Pressable
      onPress={onPress}
      accessibilityRole={onPress ? "button" : undefined}
      accessibilityLabel={`${order.buyer_login}, ${formatMoney(
        order.total_amount,
        order.currency
      )}, ${label}`}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={[styles.channel, { backgroundColor: channel.background }]}>
        <Text style={[styles.channelLabel, { color: channel.text }]} numberOfLines={1}>
          {channelLabel}
        </Text>
      </View>

      <View style={styles.middle}>
        <Text style={styles.buyer} numberOfLines={1}>
          {order.buyer_login}
        </Text>
        <Text style={styles.meta} numberOfLines={1}>
          {order.external_id.slice(0, 8).toUpperCase()} · {shortStamp(order.order_date)}
        </Text>
      </View>

      <View style={styles.right}>
        <Text style={styles.amount} numberOfLines={1}>
          {formatMoney(order.total_amount, order.currency)}
        </Text>
        <Text style={[styles.status, { color: tone.text }]} numberOfLines={1}>
          {label}
        </Text>
      </View>
    </Pressable>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
    card: {
      flexDirection: "row",
      alignItems: "center",
      gap: 12,
      borderRadius: radii.lg,
      backgroundColor: c.card,
      borderWidth: 1,
      borderColor: c.line,
      paddingVertical: 13,
      paddingHorizontal: 15,
      marginBottom: 8,
    },
    pressed: {
      opacity: 0.85,
    },
    channel: {
      // STAŁE 60 px - bez tego nazwiska nie stoją w jednej linii pionowej.
      width: 60,
      borderRadius: 5,
      paddingVertical: 3,
      alignItems: "center",
      justifyContent: "center",
    },
    channelLabel: {
      ...fonts.channel,
    },
    middle: {
      flex: 1,
      minWidth: 0,
      gap: 2,
    },
    buyer: {
      ...fonts.rowName,
      color: c.tx,
    },
    meta: {
      ...fonts.mono,
      fontSize: 10.5,
      color: c.tx3,
    },
    right: {
      alignItems: "flex-end",
      gap: 2,
    },
    amount: {
      ...fonts.amount,
      color: c.tx,
    },
    status: {
      ...fonts.status,
    },
  });
