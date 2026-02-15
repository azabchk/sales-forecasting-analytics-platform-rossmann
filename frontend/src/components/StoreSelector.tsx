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
  includeAllOption?: boolean;
}) {
  return (
    <div className="field">
      <label htmlFor="store-select">{props.label || "Store"}</label>
      <select
        id="store-select"
        className="select"
        value={props.value ?? ""}
        onChange={(e) => {
          const raw = e.target.value;
          props.onChange(raw ? Number(raw) : undefined);
        }}
      >
        {props.includeAllOption !== false && <option value="">All stores</option>}
        {props.stores.map((store) => (
          <option key={store.store_id} value={store.store_id}>
            #{store.store_id} {store.store_type ? `(${store.store_type})` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
