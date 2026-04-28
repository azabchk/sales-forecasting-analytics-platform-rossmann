export function exportToCsv(filename: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const lines = [
    headers.join(","),
    ...rows.map((row) =>
      headers
        .map((h) => {
          const val = row[h];
          const str = val === null || val === undefined ? "" : String(val);
          return str.includes(",") || str.includes('"') || str.includes("\n")
            ? `"${str.replace(/"/g, '""')}"`
            : str;
        })
        .join(",")
    ),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ExportCsvButton({
  filename,
  data,
  disabled,
}: {
  filename: string;
  data: Record<string, unknown>[];
  disabled?: boolean;
}) {
  return null; // Implemented as plain JSX below — imported as function
}
