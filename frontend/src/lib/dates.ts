export type DateRange = {
  from: string;
  to: string;
};

export function toIsoDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

export function rangeFromPastDays(days: number): DateRange {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - days);
  return {
    from: toIsoDate(from),
    to: toIsoDate(to),
  };
}

export function rangeYtd(): DateRange {
  const now = new Date();
  return {
    from: `${now.getFullYear()}-01-01`,
    to: toIsoDate(now),
  };
}

