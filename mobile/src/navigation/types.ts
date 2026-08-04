/** Parametry nawigacji - jedno źródło prawdy dla typów ekranów. */
import type { NavigatorScreenParams } from "@react-navigation/native";

/**
 * Pięć zakładek podglądu (sekcja 6.2). Kolejność odpowiada kolejności
 * na pasku; ekran "Home" został usunięty - jego rolę przejął wspólny
 * nagłówek nad zakładkami.
 */
export type MainTabParamList = {
  Orders: undefined;
  Discussions: undefined;
  Stock: undefined;
  Mailbox: undefined;
  Returns: undefined;
};

export type RootStackParamList = {
  Login: undefined;
  Lock: undefined;
  BiometricOptIn: undefined;
  Main: NavigatorScreenParams<MainTabParamList>;
  OrderDetail: { externalId: string };
  StockItem: { sku: string };
  IssueDetail: { issueId: string };
  MailDetail: { messageId: string };
  Settings: undefined;
};

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace ReactNavigation {
    interface RootParamList extends RootStackParamList {}
  }
}
