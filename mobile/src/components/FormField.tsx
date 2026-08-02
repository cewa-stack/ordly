/**
 * Pole formularza z wiodącą ikoną i etykietą - §15.6: wys. 56 pt,
 * radius 14, fokus = border primary.
 */
import * as React from "react";
import { Pressable, StyleSheet, Text, TextInput, View, type TextInputProps } from "react-native";

import { colors } from "@/theme/colors";
import { radii, spacing, typography } from "@/theme/typography";

interface FormFieldProps extends Omit<TextInputProps, "style"> {
  label: string;
  icon?: React.ReactNode;
  trailing?: React.ReactNode;
  onTrailingPress?: () => void;
  error?: boolean;
}

export function FormField({
  label,
  icon,
  trailing,
  onTrailingPress,
  error,
  onFocus,
  onBlur,
  ...inputProps
}: FormFieldProps) {
  const [focused, setFocused] = React.useState(false);
  return (
    <View style={styles.field}>
      <Text style={[styles.label, focused && styles.labelFocused]}>{label}</Text>
      <View
        style={[
          styles.row,
          focused && styles.rowFocused,
          error && styles.rowError,
        ]}
      >
        {icon}
        <TextInput
          {...inputProps}
          placeholderTextColor={colors.textDim}
          style={styles.input}
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            onBlur?.(e);
          }}
        />
        {trailing ? (
          onTrailingPress ? (
            <Pressable onPress={onTrailingPress} hitSlop={8}>
              {trailing}
            </Pressable>
          ) : (
            trailing
          )
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  field: {
    gap: 6,
  },
  label: {
    ...typography.caption,
    color: colors.textSecondary,
  },
  labelFocused: {
    color: colors.primary,
  },
  row: {
    height: 52,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: spacing.lg,
  },
  rowFocused: {
    borderColor: colors.primary,
  },
  rowError: {
    borderColor: colors.danger,
  },
  input: {
    flex: 1,
    height: "100%",
    padding: 0,
    color: colors.text,
    fontSize: 15,
  },
});
