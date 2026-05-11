import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type ConfirmModalProps = {
  open: boolean;
  title: string;
  message?: string;
  inputLabel?: string;
  inputPlaceholder?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "danger";
  onConfirm: (value?: string) => void;
  onCancel: () => void;
};

export default function ConfirmModal({
  open,
  title,
  message,
  inputLabel,
  inputPlaceholder,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setValue("");
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  const handleConfirm = () => onConfirm(inputLabel ? value : undefined);

  return createPortal(
    <div className="modal-overlay" onClick={onCancel} role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h3 id="modal-title" className="modal-title">{title}</h3>
        {message && <p className="modal-message">{message}</p>}
        {inputLabel && (
          <div className="modal-input-group">
            <label className="modal-label">{inputLabel}</label>
            <input
              ref={inputRef}
              className="modal-input"
              type="text"
              placeholder={inputPlaceholder ?? ""}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleConfirm(); }}
            />
          </div>
        )}
        <div className="modal-actions">
          <button className="button button-secondary" onClick={onCancel}>{cancelLabel}</button>
          <button
            className={`button ${variant === "danger" ? "button-danger" : "button-primary"}`}
            onClick={handleConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
