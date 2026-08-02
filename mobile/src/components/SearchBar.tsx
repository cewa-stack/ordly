/**
 * Pole wyszukiwania — §15.7: wys. 44 pt, radius 12, tło surface, ikona
 * `search`, podczas pisania przycisk `x` (wyczyść) po prawej.
 */
import * as React from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing } from "@/theme/typography";
import { CloseIcon, SearchIcon } from "@/icons";

interface SearchBarProps {
  value: string;
  onChangeText: (value: string) => void;
  placeholder: string;
}

export function SearchBar({ value, onChangeText, placeholder }: SearchBarProps) {
  const [focused, setFocused] = React.useState(false);
  return (
    <View style={[styles.wrap, focused && styles.wrapFocused]}>
      <SearchIcon size={18} color={colors.textSecondary} />
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.textDim}
        style={styles.input}
        autoCapitalize="none"
        autoCorrect={false}
        returnKeyType="search"
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
      />
      {value.length > 0 ? (
        <Pressable onPress={() => onChangeText("")} hitSlop={8}>
          <CloseIcon size={16} color={colors.textSecondary} />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    height: 44,
    backgroundColor: colors.surface,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  wrapFocused: {
    borderColor: colors.primary,
  },
  input: {
    flex: 1,
    fontSize: 15,
    color: colors.text,
    padding: 0,
  },
});
