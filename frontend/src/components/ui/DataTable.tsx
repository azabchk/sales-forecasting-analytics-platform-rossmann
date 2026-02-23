import React from "react";

type DataTableProps = {
  children: React.ReactNode;
};

export default function DataTable({ children }: DataTableProps) {
  return (
    <div className="table-wrap">
      <table className="table">{children}</table>
    </div>
  );
}
