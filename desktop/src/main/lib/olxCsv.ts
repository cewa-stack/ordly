/**
 * Parser CSV do importu ofert OLX (Wariant B, patrz olxStore.ts).
 *
 * Wlasny, prosty format (title,price,stock,url,sku) - nie zaklada
 * konkretnego eksportu z panelu OLX, ktorego ksztaltu nie da sie
 * potwierdzic bez dostepu do konta z aktywnymi ogloszeniami. Obsluguje
 * pola w cudzyslowach (przecinki w tytule).
 */
export interface OlxCsvRow {
  title: string;
  price: number;
  stock: number;
  url: string;
  linkedSku?: string;
}

function parseCsvLine(line: string): string[] {
  const cells: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (inQuotes) {
      if (char === '"') {
        if (line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        current += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      cells.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current);
  return cells;
}

export function parseOlxCsv(content: string): OlxCsvRow[] {
  const lines = content.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length < 2) {
    return [];
  }
  const header = parseCsvLine(lines[0]).map((h) => h.trim().toLowerCase());
  const titleIdx = header.indexOf("title");
  const priceIdx = header.indexOf("price");
  const stockIdx = header.indexOf("stock");
  const urlIdx = header.indexOf("url");
  const skuIdx = header.indexOf("sku");

  const rows: OlxCsvRow[] = [];
  for (const line of lines.slice(1)) {
    const cells = parseCsvLine(line);
    const title = titleIdx >= 0 ? cells[titleIdx]?.trim() : undefined;
    if (!title) {
      continue;
    }
    rows.push({
      title,
      price: priceIdx >= 0 ? Number(cells[priceIdx]) || 0 : 0,
      stock: stockIdx >= 0 ? Number(cells[stockIdx]) || 0 : 0,
      url: urlIdx >= 0 ? (cells[urlIdx]?.trim() ?? "") : "",
      linkedSku: skuIdx >= 0 ? cells[skuIdx]?.trim() || undefined : undefined,
    });
  }
  return rows;
}
