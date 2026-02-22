function resolveLocale(): string {
  const lang = document.documentElement.lang;
  return lang === "ru" ? "ru-RU" : "en-US";
}

export function formatInt(value: number): string {
  const numberFormatter = new Intl.NumberFormat(resolveLocale(), {
    maximumFractionDigits: 0,
  });
  return numberFormatter.format(value);
}

export function formatDecimal(value: number): string {
  const decimalFormatter = new Intl.NumberFormat(resolveLocale(), {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return decimalFormatter.format(value);
}

export function formatCompact(value: number): string {
  const compactFormatter = new Intl.NumberFormat(resolveLocale(), {
    notation: "compact",
    maximumFractionDigits: 1,
  });
  return compactFormatter.format(value);
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function formatDateLabel(rawDate: string | number): string {
  const dateFormatter = new Intl.DateTimeFormat(resolveLocale(), {
    month: "short",
    day: "numeric",
  });
  const parsed = new Date(rawDate);
  if (Number.isNaN(parsed.getTime())) {
    return String(rawDate);
  }
  return dateFormatter.format(parsed);
}

export function formatMonthLabel(rawDate: string | number): string {
  const monthFormatter = new Intl.DateTimeFormat(resolveLocale(), {
    month: "short",
    year: "2-digit",
  });
  const parsed = new Date(rawDate);
  if (Number.isNaN(parsed.getTime())) {
    return String(rawDate);
  }
  return monthFormatter.format(parsed);
}
