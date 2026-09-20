/** Parametry nawigacji - jedno źródło prawdy dla typów ekranów. */
import type { NavigatorScreenParams } from "@react-navigation/native";

/**
 * Pięć zakładek (sekcja 11 instrukcji "Nokturn"). Kolejność odpowiada
 * kolejności na pasku, a `Ordlak` stoi POŚRODKU celowo - to gałka.
 *
 * Dyskusje i Zwroty zeszły z paska do stosu głównego. Nie są ślepymi
 * zaułkami: prowadzą do nich kafle i lista "Wymaga uwagi" na ekranie
 * Start, a push z powiadomienia trafia w nie tak samo jak wcześniej.
 */
export type MainTabParamList = {
  Home: undefined;
  Orders: undefined;
  Ordlak: undefined;
  Stock: undefined;
  Mailbox: undefined;
};

export type RootStackParamList = {
  Login: undefined;
  Lock: undefined;
  BiometricOptIn: undefined;
  Main: NavigatorScreenParams<MainTabParamList>;
  OrderDetail: { externalId: string };
  IssueDetail: { issueId: string };
  MailDetail: { messageId: string };
  Discussions: undefined;
  Returns: undefined;
  Settings: undefined;
};

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
