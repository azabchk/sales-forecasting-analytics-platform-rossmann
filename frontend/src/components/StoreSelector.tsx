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
  id?: string;
}) {
  const selectId = props.id || "store-select";

  return (
    <div className="field">
      <label htmlFor={selectId}>{props.label || "Store"}</label>
      <select
        id={selectId}
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
