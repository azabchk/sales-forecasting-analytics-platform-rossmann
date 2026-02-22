import React from "react";
import { useI18n } from "../lib/i18n";

type Store = {
  store_id: number;
  store_type?: string;
};

function formatStoreTypeLabel(storeType: string | undefined, locale: "en" | "ru"): string {
  if (!storeType) {
    return "";
  }

  const code = storeType.trim().toLowerCase();
  if (!code) {
    return "";
  }

  if (locale === "ru") {
    return `Тип ${code.toUpperCase()}`;
  }
  return `Type ${code.toUpperCase()}`;
}

export default function StoreSelector(props: {
  stores: Store[];
  value?: number;
  onChange: (storeId?: number) => void;
  label?: string;
  includeAllOption?: boolean;
  id?: string;
}) {
  const { locale } = useI18n();
  const selectId = props.id || "store-select";

  return (
    <div className="field">
      <label htmlFor={selectId}>{props.label || (locale === "ru" ? "Магазин" : "Store")}</label>
      <select
        id={selectId}
        className="select"
        value={props.value ?? ""}
        onChange={(e) => {
          const raw = e.target.value;
          props.onChange(raw ? Number(raw) : undefined);
        }}
      >
        {props.includeAllOption !== false && <option value="">{locale === "ru" ? "Все магазины" : "All stores"}</option>}
        {props.stores.map((store) => {
          const storeTypeLabel = formatStoreTypeLabel(store.store_type, locale);
          return (
            <option key={store.store_id} value={store.store_id}>
              #{store.store_id}
              {storeTypeLabel ? ` - ${storeTypeLabel}` : ""}
            </option>
          );
        })}
      </select>
    </div>
  );
}
