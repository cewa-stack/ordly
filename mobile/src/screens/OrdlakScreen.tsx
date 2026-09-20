/**
 * Ordlak - ekran asystenta (sekcja 13 instrukcji "Nokturn").
 *
 * Mobilny odpowiednik desktopowego paska "Zapytaj Ordlaka". Środkowa
 * zakładka (gałka) prowadzi tutaj.
 *
 * BACKEND JUŻ ISTNIEJE. Sekcja 13 wymienia `POST /assistant/ask` jako
 * rzecz do dorobienia - ale Pi od czasu desktopu wystawia
 * `POST /api/v1/ordlak/chat` z tym samym kontraktem, własnym zakresem
 * sesji i zapisem obu wypowiedzi przed odpowiedzią. Telefon go po prostu
 * woła; nowy endpoint byłby drugim wejściem do tej samej logiki.
 *
 * DZIAŁANIA (decyzja 3 z sekcji 16 - "może zapisywać, ma być przydatny"):
 * Ordlak potrafi PRZYGOTOWAĆ trzy rzeczy - wpisanie stanu na półce,
 * oznaczenie zamówienia i odpowiedź w dyskusji. Przychodzą jako pole
 * `actions` przy odpowiedzi i pokazują się jako przyciski. Zapis dzieje
 * się dopiero po naciśnięciu, zapytaniem `POST /api/v1/ordlak/apply`.
 *
 * Dwa z tych działań widzi kupujący, więc mają potwierdzenie z osobnym
 * ekranem - "Wyślij odpowiedź" nie jest rzeczą, którą chce się nacisnąć
 * przypadkiem, przewijając listę kciukiem.
 *
 * Propozycje żyją tylko w BIEŻĄCEJ sesji: backend ich nie zapisuje, więc
 * po powrocie do wątku przycisków nie ma. To celowe - propozycja sprzed
 * trzech dni nie ma prawa być jedno dotknięcie od wykonania.
 *
 * ODSTĘPSTWO OD INSTRUKCJI: mikrofon pokazuje się TYLKO tam, gdzie da się
 * nagrywać - czyli w PWA, w przeglądarce z Web Speech API. Na natywnym
 * iOS/Androidzie projekt nie ma modułu rozpoznawania mowy, więc ikona by
 * nie działała.
 */
import * as React from "react";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import * as Clipboard from "expo-clipboard";
import { LinearGradient } from "expo-linear-gradient";

import type { Palette } from "@/theme/colors";
import { useTheme, useThemedStyles } from "@/theme/theme";
import { fonts, radii, spacing } from "@/theme/typography";
import { TabHeading } from "@/components/TabHeading";
import { Ordlak } from "@/components/Ordlak";
import { ArrowUpIcon, MicIcon } from "@/icons";
import {
  useApplyAssistantAction,
  useAskOrdlak,
  useOrdlakConversation,
  useOrdlakStatus,
} from "@/api/hooks";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import type { AssistantAction, OrdlakStoredMessage } from "@/api/types";

/**
 * Podpowiedzi są CZYNNOŚCIOWE - mówią, co Ordlak może zrobić, a nie
 * "zapytaj o cokolwiek". Każda dotyczy danych, które asystent naprawdę
 * czyta ze swoich narzędzi.
 */
const SUGGESTIONS = [
  "Podsumuj dzień",
  "Co czeka na spakowanie?",
  "Czego brakuje na półce?",
  "Pokaż otwarte dyskusje",
  "Ile zarobiłem w tym miesiącu?",
];

/** Odpowiedź warta własnej karty - dłuższa niż zdanie albo wielolinijkowa. */
function isResultWorthy(text: string): boolean {
  return text.length > 220 || text.split("\n").length > 3;
}

function useSpeechInput(onResult: (text: string) => void) {
  // Web Speech API istnieje tylko w przeglądarce - na natywnym RN nie ma
  // odpowiednika bez dodatkowego modułu, więc mikrofon się tam nie pokazuje.
  const supported =
    Platform.OS === "web" &&
    typeof window !== "undefined" &&
    Boolean(
      (window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown })
        .SpeechRecognition ??
        (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition
    );
  const [listening, setListening] = React.useState(false);

  const start = React.useCallback(() => {
    if (!supported) return;
    const Ctor =
      (window as unknown as { SpeechRecognition?: new () => never }).SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: new () => never })
        .webkitSpeechRecognition;
    if (!Ctor) return;
    const recognition = new (Ctor as unknown as new () => {
      lang: string;
      interimResults: boolean;
      onresult: (event: { results: { 0: { 0: { transcript: string } } } }) => void;
      onend: () => void;
      onerror: () => void;
      start: () => void;
    })();
    recognition.lang = "pl-PL";
    recognition.interimResults = false;
    recognition.onresult = (event) => onResult(event.results[0][0].transcript);
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);
    setListening(true);
    recognition.start();
  }, [supported, onResult]);

  return { supported, listening, start };
}

/** Wiadomość użytkownika - dymek DOSUNIĘTY W PRAWO. */
function UserBubble({ text }: { text: string }) {
  const styles = useThemedStyles(createStyles);
  return (
    <View style={styles.userRow}>
      <View style={styles.userBubble}>
        <Text style={styles.userText}>{text}</Text>
      </View>
    </View>
  );
}

/**
 * Odpowiedź Ordlaka - BEZ DYMKA. Dymek tylko po stronie użytkownika;
 * to odróżnia strony bez malowania połowy ekranu na kolor.
 */
function AssistantMessage({
  text,
  tools,
  actions = [],
  onRunAction,
  runningKind,
  doneKinds,
}: {
  text: string;
  tools: string[];
  actions?: AssistantAction[];
  onRunAction?: (action: AssistantAction) => void;
  runningKind?: string | null;
  doneKinds?: string[];
}) {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();
  const [copied, setCopied] = React.useState(false);

  async function copy() {
    await Clipboard.setStringAsync(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  return (
    <View style={styles.assistantRow}>
      <Ordlak state="idle" size={28} />
      <View style={styles.assistantCopy}>
        <Text style={styles.assistantText}>{text}</Text>

        {/*
          Propozycje działań. Nic się jeszcze nie wydarzyło - dopóki
          użytkownik nie naciśnie, to tylko tekst na ekranie.
        */}
        {actions.map((action) => {
          const done = doneKinds?.includes(action.kind);
          const running = runningKind === action.kind;
          return (
            <View key={action.kind} style={styles.actionCard}>
              <Text style={styles.actionSummary}>{action.summary}</Text>
              <Pressable
                onPress={() => onRunAction?.(action)}
                disabled={done || running || !onRunAction}
                accessibilityRole="button"
                accessibilityLabel={`${action.label}. ${action.summary}`}
                style={({ pressed }) => [
                  styles.actionButton,
                  action.outward && styles.actionButtonOutward,
                  (done || running) && styles.actionButtonDone,
                  pressed && styles.pressed,
                ]}
              >
                {running ? (
                  <ActivityIndicator size="small" color={c.onAcc} />
                ) : (
                  <Text
                    style={[
                      styles.actionButtonText,
                      action.outward && { color: c.onAcc },
                    ]}
                  >
                    {done ? "Zrobione" : action.label}
                  </Text>
                )}
              </Pressable>
            </View>
          );
        })}

        {isResultWorthy(text) && (
          <View style={styles.resultCard}>
            <Text style={styles.resultHead} numberOfLines={1}>
              Odpowiedź Ordlaka
              {tools.length > 0 ? ` · ${tools.join(", ")}` : ""}
            </Text>
            <View style={styles.resultActions}>
              <Pressable
                onPress={copy}
                accessibilityRole="button"
                style={({ pressed }) => [styles.pillSolid, pressed && styles.pressed]}
              >
                <Text style={styles.pillSolidText}>{copied ? "Skopiowano" : "Kopiuj"}</Text>
              </Pressable>
              <Pressable
                onPress={() => void Share.share({ message: text })}
                accessibilityRole="button"
                style={({ pressed }) => [styles.pillOutline, pressed && styles.pressed]}
              >
                <Text style={styles.pillOutlineText}>Udostępnij</Text>
              </Pressable>
            </View>
          </View>
        )}

        {tools.length > 0 && !isResultWorthy(text) && (
          <Text style={[styles.toolsNote, { color: c.tx3 }]} numberOfLines={1}>
            dane z: {tools.join(", ")}
          </Text>
        )}
      </View>
    </View>
  );
}

export function OrdlakScreen() {
  const styles = useThemedStyles(createStyles);
  const { c } = useTheme();

  const [draft, setDraft] = React.useState("");
  const [conversationId, setConversationId] = React.useState<number | null>(null);
  const [pendingQuestion, setPendingQuestion] = React.useState<string | null>(null);
  const scrollRef = React.useRef<ScrollView>(null);

  const status = useOrdlakStatus();
  const thread = useOrdlakConversation(conversationId);
  const ask = useAskOrdlak();
  const applyAction = useApplyAssistantAction();

  /** Działanie czekające na potwierdzenie (tylko te widoczne na zewnątrz). */
  const [pendingAction, setPendingAction] = React.useState<AssistantAction | null>(null);
  /** Rodzaje już wykonane - przycisk zmienia się w „Zrobione". */
  const [doneKinds, setDoneKinds] = React.useState<string[]>([]);
  const [actionNote, setActionNote] = React.useState<string | null>(null);

  /**
   * Kopia lokalna tej rozmowy. Odpowiedz przychodzi z `POST /ordlak/chat`,
   * ale historie rysuje `GET /ordlak/conversations/{id}` - gdyby ekran
   * czekal wylacznie na to drugie zapytanie, to przy wolnym laczu albo
   * jego bledzie pytanie i odpowiedz znikalyby z ekranu zaraz po
   * wyslaniu. Kopia lokalna trzyma je do czasu, az watek wroci z Pi.
   */
  const [localTurns, setLocalTurns] = React.useState<OrdlakStoredMessage[]>([]);

  const configured = status.data?.configured ?? true;
  const serverMessages: OrdlakStoredMessage[] = thread.data?.messages ?? [];
  // Wersja z Pi jest nadrzedna - ma pelna historie, nie tylko biezaca turę.
  const messages = serverMessages.length > 0 ? serverMessages : localTurns;

  const speech = useSpeechInput(React.useCallback((text: string) => setDraft(text), []));

  React.useEffect(() => {
    scrollRef.current?.scrollToEnd({ animated: true });
  }, [messages.length, pendingQuestion, ask.isPending]);

  function send(text: string) {
    const question = text.trim();
    if (!question || ask.isPending || !configured) return;
    setDraft("");
    setPendingQuestion(question);
    const askedAt = new Date().toISOString();
    ask.mutate(
      { message: question, conversationId },
      {
        onSuccess: (reply) => {
          setConversationId(reply.conversation_id);
          setLocalTurns((prev) => [
            ...prev,
            { role: "user", content: question, created_at: askedAt, used_tools: [] },
            {
              role: "assistant",
              content: reply.reply,
              created_at: new Date().toISOString(),
              used_tools: reply.used_tools ?? [],
              // Propozycje żyją tylko tutaj - backend ich nie zapisuje.
              actions: reply.actions ?? [],
            },
          ]);
        },
        onSettled: () => setPendingQuestion(null),
      }
    );
  }

  function runAction(action: AssistantAction) {
    // Działanie widoczne na zewnątrz (Allegro, kupujący) dostaje osobne
    // pytanie. Lokalne - stan na półce - wykonuje się od razu, bo da się
    // je poprawić następnym zdaniem.
    if (action.outward) {
      setPendingAction(action);
      return;
    }
    confirmAction(action);
  }

  function confirmAction(action: AssistantAction) {
    setPendingAction(null);
    applyAction.mutate(action, {
      onSuccess: (result) => {
        setDoneKinds((prev) => [...prev, action.kind]);
        setActionNote(result.message);
      },
      onError: () => {
        setActionNote("Nie udało się wykonać. Sprawdź połączenie z Pi.");
      },
    });
  }

  const empty = messages.length === 0 && !pendingQuestion && !ask.isPending;

  return (
    <View style={styles.screen}>
      <TabHeading title="Ordlak" count="Asystent · działa na Twoim Pi" />

      <View style={styles.conversationWrap}>
        <ScrollView
          ref={scrollRef}
          contentContainerStyle={[styles.conversation, empty && styles.conversationEmpty]}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {!configured && (
            <View style={styles.notice}>
              <Text style={styles.noticeText}>
                Ordlak nie ma klucza API na Pi, więc nie odpowie. Uzupełnij{" "}
                <Text style={styles.code}>ANTHROPIC_API_KEY</Text> w{" "}
                <Text style={styles.code}>~/ordly/backend/.env</Text> i zrestartuj usługę:{" "}
                <Text style={styles.code}>sudo systemctl restart ordly</Text>.
              </Text>
            </View>
          )}

          {empty && configured && (
            <View style={styles.intro}>
              <Ordlak state="idle" size={62} />
              <Text style={styles.introTitle}>Zapytaj o swój sklep</Text>
              <Text style={styles.introBody}>
                Ordlak czyta te same dane co reszta aplikacji — sprzedaż, magazyn, zwroty,
                dyskusje i skrzynkę. Liczby bierze z bazy, nie z pamięci.
              </Text>
            </View>
          )}

          {messages.map((message, index) =>
            message.role === "user" ? (
              <UserBubble key={index} text={message.content} />
            ) : (
              <AssistantMessage
                key={index}
                text={message.content}
                tools={message.used_tools ?? []}
                actions={message.actions}
                onRunAction={runAction}
                runningKind={applyAction.isPending ? pendingAction?.kind ?? null : null}
                doneKinds={doneKinds}
              />
            )
          )}

          {pendingQuestion && <UserBubble text={pendingQuestion} />}

          {ask.isPending && (
            <View style={styles.assistantRow}>
              {/* `think` dopóki model naprawdę liczy - nie "na wszelki wypadek". */}
              <Ordlak state="think" size={28} />
              {/* Stan pośredni kursywą w tx3 (sekcja 13). */}
              <Text style={styles.thinking}>Przeglądam dane w bazie…</Text>
            </View>
          )}

          {ask.isError && !ask.isPending && (
            <Text style={styles.error}>
              Odpowiedź nie doszła. Sprawdź połączenie z Pi i spróbuj ponownie.
            </Text>
          )}

          {actionNote && <Text style={styles.actionNote}>{actionNote}</Text>}
        </ScrollView>

        {/* Wygaszenie OD GÓRY (odwrotnie niż na listach) - sekcja 13. */}
        <LinearGradient
          colors={[c.bg, "transparent"]}
          style={styles.fadeTop}
          pointerEvents="none"
        />
      </View>

      {/* ------------------------------------------------ podpowiedzi */}
      {/*
        `flexGrow: 0` jest OBOWIAZKOWE. Pozioma lista w kolumnie flex
        zabiera cala wolna wysokosc, a chipy rozciagaja sie wtedy na pol
        ekranu - pastylka 30 px robi sie slupem.
      */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.suggestionsBar}
        contentContainerStyle={styles.suggestions}
        keyboardShouldPersistTaps="handled"
      >
        {SUGGESTIONS.map((suggestion) => (
          <Pressable
            key={suggestion}
            onPress={() => send(suggestion)}
            disabled={!configured || ask.isPending}
            accessibilityRole="button"
            style={({ pressed }) => [styles.chip, pressed && styles.pressed]}
          >
            <Text style={styles.chipText}>{suggestion}</Text>
          </Pressable>
        ))}
      </ScrollView>

      {/* ------------------------------------------------ pole tekstu */}
      <View style={styles.composer}>
        <TextInput
          value={draft}
          onChangeText={setDraft}
          placeholder={speech.listening ? "Słucham…" : "Zapytaj o swój sklep…"}
          placeholderTextColor={c.tx3}
          editable={configured && !ask.isPending}
          onSubmitEditing={() => send(draft)}
          returnKeyType="send"
          style={styles.input}
        />
        {/* Mikrofon należy do grupy akcji po prawej, nie do pola tekstowego. */}
        {speech.supported && (
          <Pressable
            onPress={speech.start}
            accessibilityRole="button"
            accessibilityLabel="Podyktuj pytanie"
            hitSlop={8}
            style={styles.mic}
          >
            <MicIcon size={18} color={speech.listening ? c.acc : c.tx3} />
          </Pressable>
        )}
        <Pressable
          onPress={() => send(draft)}
          disabled={draft.trim().length === 0 || ask.isPending || !configured}
          accessibilityRole="button"
          accessibilityLabel="Wyślij pytanie"
          style={({ pressed }) => [
            styles.send,
            (draft.trim().length === 0 || ask.isPending || !configured) && styles.sendDisabled,
            pressed && styles.pressed,
          ]}
        >
          {ask.isPending ? (
            <ActivityIndicator size="small" color={c.onAcc} />
          ) : (
            <ArrowUpIcon size={16} color={c.onAcc} />
          )}
        </Pressable>
      </View>

      {/*
        Potwierdzenie dla działań, które widzi kupujący. `summary` z Pi
        mówi wprost, co się stanie i że nie da się tego cofnąć.
      */}
      <ConfirmDialog
        visible={pendingAction !== null}
        title={pendingAction?.label ?? ""}
        description={pendingAction?.summary}
        confirmLabel={pendingAction?.label ?? "Wykonaj"}
        busy={applyAction.isPending}
        onConfirm={() => pendingAction && confirmAction(pendingAction)}
        onCancel={() => setPendingAction(null)}
      />
    </View>
  );
}

const createStyles = (c: Palette) =>
  StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: c.bg,
    },
    conversationWrap: {
      flex: 1,
      minHeight: 0,
    },
    conversation: {
      flexGrow: 1,
      // Rozmowa "siada" na dole - nowa wiadomość wchodzi od spodu.
      justifyContent: "flex-end",
      gap: 12,
      paddingHorizontal: spacing.xl,
      paddingTop: 34,
      paddingBottom: spacing.md,
    },
    conversationEmpty: {
      justifyContent: "center",
    },
    fadeTop: {
      position: "absolute",
      left: 0,
      right: 0,
      top: 0,
      height: 34,
    },
    pressed: {
      opacity: 0.8,
    },

    intro: {
      alignItems: "center",
      gap: 10,
      paddingHorizontal: spacing.lg,
    },
    introTitle: {
      ...fonts.panelTitle,
      color: c.tx,
    },
    introBody: {
      ...fonts.body,
      color: c.tx3,
      textAlign: "center",
    },

    notice: {
      borderRadius: radii.md,
      backgroundColor: c.card,
      borderWidth: 1,
      borderColor: c.line2,
      padding: 12,
    },
    noticeText: {
      ...fonts.body,
      color: c.tx2,
    },
    code: {
      ...fonts.mono,
      fontSize: 11,
      color: c.tx,
    },

    userRow: {
      alignItems: "flex-end",
    },
    userBubble: {
      maxWidth: "78%",
      backgroundColor: c.accDim,
      borderTopLeftRadius: 17,
      borderTopRightRadius: 17,
      borderBottomRightRadius: 5,
      borderBottomLeftRadius: 17,
      paddingVertical: 10,
      paddingHorizontal: 14,
    },
    userText: {
      ...fonts.rowName,
      fontSize: 13,
      color: c.tx,
    },

    assistantRow: {
      flexDirection: "row",
      gap: 10,
      alignItems: "flex-start",
    },
    assistantCopy: {
      flex: 1,
      minWidth: 0,
    },
    assistantText: {
      ...fonts.body,
      fontSize: 13,
      lineHeight: 19,
      color: c.tx,
    },
    thinking: {
      ...fonts.body,
      fontSize: 13,
      fontStyle: "italic",
      color: c.tx3,
      paddingTop: 5,
    },
    error: {
      ...fonts.body,
      color: c.coral,
    },
    toolsNote: {
      ...fonts.mono,
      fontSize: 9.5,
      marginTop: 5,
    },

    actionCard: {
      marginTop: 9,
      borderRadius: radii.md,
      backgroundColor: c.card,
      borderWidth: 1,
      borderColor: c.line2,
      paddingVertical: 11,
      paddingHorizontal: 12,
      gap: 9,
    },
    actionSummary: {
      ...fonts.body,
      color: c.tx2,
    },
    actionButton: {
      alignSelf: "flex-start",
      borderRadius: radii.full,
      borderWidth: 1,
      borderColor: c.line2,
      paddingVertical: 8,
      paddingHorizontal: 15,
      minHeight: 34,
      justifyContent: "center",
    },
    actionButtonOutward: {
      // Działanie nieodwracalne dostaje pełne wypełnienie - ma być
      // widać, że to nie jest kolejny chip do przewinięcia.
      backgroundColor: c.acc,
      borderColor: "transparent",
    },
    actionButtonDone: {
      opacity: 0.5,
    },
    actionButtonText: {
      ...fonts.status,
      fontSize: 12,
      color: c.tx,
    },
    actionNote: {
      ...fonts.body,
      color: c.acc,
      paddingLeft: 38,
    },
    resultCard: {
      marginTop: 9,
      borderRadius: radii.md,
      backgroundColor: c.card,
      borderWidth: 1,
      borderColor: c.line,
      paddingVertical: 11,
      paddingHorizontal: 12,
      gap: 9,
    },
    resultHead: {
      ...fonts.eyebrow,
      fontSize: 9,
      color: c.tx3,
    },
    resultActions: {
      flexDirection: "row",
      gap: spacing.sm,
    },
    pillSolid: {
      backgroundColor: c.acc,
      borderRadius: radii.full,
      paddingVertical: 6,
      paddingHorizontal: 13,
    },
    pillSolidText: {
      ...fonts.status,
      fontSize: 11.5,
      color: c.onAcc,
    },
    pillOutline: {
      borderWidth: 1,
      borderColor: c.line2,
      borderRadius: radii.full,
      paddingVertical: 6,
      paddingHorizontal: 13,
    },
    pillOutlineText: {
      ...fonts.status,
      fontSize: 11.5,
      color: c.tx2,
    },

    suggestionsBar: {
      flexGrow: 0,
      flexShrink: 0,
    },
    suggestions: {
      gap: spacing.sm,
      alignItems: "center",
      paddingHorizontal: spacing.xl,
      paddingBottom: 10,
    },
    chip: {
      borderWidth: 1,
      borderColor: c.line2,
      borderRadius: radii.full,
      paddingVertical: 6,
      paddingHorizontal: 11,
    },
    chipText: {
      ...fonts.caption,
      fontSize: 11.5,
      color: c.tx2,
    },

    composer: {
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.sm,
      height: 46,
      borderRadius: radii.full,
      backgroundColor: c.card,
      borderWidth: 1,
      borderColor: c.line,
      marginHorizontal: spacing.xl,
      marginBottom: spacing.md,
      paddingLeft: 16,
      paddingRight: 5,
    },
    input: {
      flex: 1,
      minWidth: 0,
      ...fonts.body,
      fontSize: 13.5,
      color: c.tx,
      padding: 0,
    },
    mic: {
      // Mikrofon należy do grupy akcji po prawej, nie do pola.
      marginLeft: "auto",
    },
    send: {
      width: 36,
      height: 36,
      borderRadius: 18,
      backgroundColor: c.acc,
      alignItems: "center",
      justifyContent: "center",
    },
    sendDisabled: {
      opacity: 0.4,
    },
  });
