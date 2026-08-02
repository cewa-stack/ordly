/** Parametry nawigacji - jedno źródło prawdy dla typów ekranów. */
import type { NavigatorScreenParams } from "@react-navigation/native";

export type MainTabParamList = {
  Home: undefined;
  Orders: undefined;
  Stock: undefined;
  Returns: undefined;
  Discussions: undefined;
  Mailbox: undefined;
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
