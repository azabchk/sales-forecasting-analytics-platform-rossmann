import React from "react";

type Store = {
  store_id: number;
  store_type?: string;
};

export default function StoreSelector(props: {
  stores: Store[];
  value?: number;
  onChange: (storeId?: number) => void;
  label?: string;
}) {
  return (
    <label style={{ display: "block", marginBottom: 8 }}>
      <span style={{ display: "block", marginBottom: 4 }}>{props.label || "Магазин"}</span>
      <select
        value={props.value ?? ""}
        onChange={(e) => {
          const raw = e.target.value;
          props.onChange(raw ? Number(raw) : undefined);
        }}
        style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid #c8d4f1", minWidth: 220 }}
      >
        <option value="">Все магазины</option>
        {props.stores.map((store) => (
          <option key={store.store_id} value={store.store_id}>
            #{store.store_id} {store.store_type ? `(${store.store_type})` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
