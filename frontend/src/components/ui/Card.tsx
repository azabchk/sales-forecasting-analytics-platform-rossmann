import React from "react";

type CardProps = {
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
};

export default function Card({ title, subtitle, actions, className = "", children }: CardProps) {
  return (
    <section className={`panel ${className}`.trim()}>
      {(title || subtitle || actions) && (
        <div className="panel-head">
          <div>
            {title ? <h3>{title}</h3> : null}
            {subtitle ? <p className="panel-subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div>{actions}</div> : null}
        </div>
      )}
      {children}
    </section>
  );
}
