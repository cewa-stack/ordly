/**
 * Pole wyszukiwania — §15.7: wys. 44 pt, radius 12, tło surface, ikona
 * `search`, podczas pisania przycisk `x` (wyczyść) po prawej.
 */
import * as React from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";

import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { radii, spacing } from "@/theme/typography";
import { CloseIcon, SearchIcon } from "@/icons";

interface SearchBarProps {
  value: string;
  onChangeText: (value: string) => void;
  placeholder: string;
}

export function SearchBar({ value, onChangeText, placeholder }: SearchBarProps) {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
  const [focused, setFocused] = React.useState(false);
  return (
    <View style={[styles.wrap, focused && styles.wrapFocused]}>
      <SearchIcon size={18} color={c.tx2} />
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={c.tx3}
        style={styles.input}
        autoCapitalize="none"
        autoCorrect={false}
        returnKeyType="search"
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
      />
      {value.length > 0 ? (
        <Pressable onPress={() => onChangeText("")} hitSlop={8}>
          <CloseIcon size={16} color={c.tx2} />
        </Pressable>
      ) : null}
    </View>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    height: 44,
    backgroundColor: c.card,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: c.line,
  },
  wrapFocused: {
    borderColor: c.acc,
  },
  input: {
    flex: 1,
    fontSize: 15,
    color: c.tx,
    padding: 0,
  },
});
