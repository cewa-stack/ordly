/**
 * IPC Ordlaka - generator ofert Allegro.
 *
 * Zdjęcia przechodzą przez mostek jako zwykłe bajty (`Uint8Array`), bo
 * `File`/`Blob` nie przetrwałyby serializacji IPC. Renderer czyta plik do
 * `ArrayBuffer`, main składa z tego `multipart/form-data`.
 */
import { ipcMain } from "electron";
import { apiRequest, apiUpload, type UploadFilePart } from "../lib/apiClient";
import { requireSession } from "../lib/tokenStore";
import { toResult } from "../lib/result";

interface OrdlakPhotoInput {
  fileName: string;
  mimeType: string;
  bytes: Uint8Array;
}

interface OrdlakGenerateInput {
  note: string;
  condition: string;
  purchaseCost: number;
  inboundShippingCost: number;
  buyerShippingCost: number;
  commissionPercent: number;
  targetMarginPercent: number;
  photos?: OrdlakPhotoInput[];
}

interface OrdlakFinalizeInput {
  id: number;
  finalTitle: string;
  finalDescriptionHtml: string;
}

export function registerOrdlakIpc(): void {
  ipcMain.handle("ordly:ordlak:status", async () =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(session.baseUrl, session.token, "/api/v1/ordlak/status");
    })
  );

  ipcMain.handle("ordly:ordlak:generate", async (_event, input: OrdlakGenerateInput) =>
    toResult(async () => {
      const session = requireSession();
      const files: UploadFilePart[] = (input.photos ?? []).map((photo) => ({
        fieldName: "photos",
        fileName: photo.fileName,
        mimeType: photo.mimeType,
        bytes: photo.bytes,
      }));

      return apiUpload(
        session.baseUrl,
        session.token,
        "/api/v1/ordlak/generate",
        {
          note: input.note,
          condition: input.condition,
          purchase_cost: input.purchaseCost,
          inbound_shipping_cost: input.inboundShippingCost,
          buyer_shipping_cost: input.buyerShippingCost,
          commission_percent: input.commissionPercent,
          target_margin_percent: input.targetMarginPercent,
        },
        files
      );
    })
  );

  ipcMain.handle("ordly:ordlak:history", async (_event, limit = 20) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/ordlak/history?limit=${encodeURIComponent(String(limit))}`
      );
    })
  );

  ipcMain.handle("ordly:ordlak:finalize", async (_event, input: OrdlakFinalizeInput) =>
    toResult(async () => {
      const session = requireSession();
      return apiRequest(
        session.baseUrl,
        session.token,
        `/api/v1/ordlak/${encodeURIComponent(String(input.id))}/finalize`,
        {
          method: "POST",
          body: {
            final_title: input.finalTitle,
            final_description_html: input.finalDescriptionHtml,
          },
        }
      );
    })
  );
}
