import React from "react";

type PageLayoutProps = {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
};

export default function PageLayout({ title, subtitle, actions, children }: PageLayoutProps) {
  return (
    <section className="page">
      <div className="page-head">
        <div>
          <h2 className="page-title">{title}</h2>
          {subtitle ? <p className="page-note">{subtitle}</p> : null}
        </div>
        {actions ? <div className="inline-meta">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}
