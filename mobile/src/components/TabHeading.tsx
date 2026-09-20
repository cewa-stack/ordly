/**
 * Nagłówek ekranu (sekcja 11 instrukcji "Nokturn").
 *
 * Nazwa została z poprzedniej wersji, bo wołają go wszystkie zakładki -
 * ale to już nie jest sam wiersz "tytuł + licznik". Renderuje pełen
 * nagłówek z sekcji 11: nadtytuł wersalikami, tytuł Bricolage 24 px
 * i awatar prowadzący do Ustawień.
 *
 * Nagłówek należy teraz do EKRANU, nie do szkieletu aplikacji. Wcześniej
 * stał raz, nad nawigatorem zakładek, i mówił na każdym ekranie to samo
 * ("Cześć, lukas") - a sekcja 11 chce, żeby niósł, GDZIE jesteś.
 */
import * as React from "react";

import { AppHeader } from "./AppHeader";
import { useAuth } from "@/store/auth";

const DATE_FORMATTER = new Intl.DateTimeFormat("pl-PL", {
  weekday: "long",
  day: "numeric",
  month: "long",
});

/** Inicjały z loginu - maksymalnie dwa znaki, zawsze wersalikami. */
export function initialsOf(username: string | null | undefined): string {
  if (!username) return "?";
  const parts = username.split(/[\s._-]+/).filter(Boolean);
  const letters = parts.slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "");
  return letters.join("") || username.slice(0, 2).toUpperCase();
}

interface TabHeadingProps {
  title: string;
  /**
   * Nadtytuł. Krótka informacja o zawartości, np. "12 na liście".
   * Pominięty = dzisiejsza data, żeby wiersz nigdy nie był pusty.
   */
  count?: string;
  /** Słowo z tytułu, które świeci akcentem (musi być jego fragmentem). */
  accent?: string;
}

export function TabHeading({ title, count, accent }: TabHeadingProps) {
  const { username } = useAuth();
  return (
    <AppHeader
      eyebrow={count ?? DATE_FORMATTER.format(new Date())}
      title={title}
      accent={accent}
      initials={initialsOf(username)}
    />
  );
}
