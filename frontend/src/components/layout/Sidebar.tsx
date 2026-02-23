import React from "react";
import { NavLink } from "react-router-dom";

type SidebarItem = {
  to: string;
  label: string;
};

type SidebarSection = {
  title: string;
  items: SidebarItem[];
};

type SidebarProps = {
  sections: SidebarSection[];
};

export default function Sidebar({ sections }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <p className="sidebar-eyebrow">Sales Forecasting</p>
        <h1 className="sidebar-title">Rossmann Platform v2</h1>
      </div>
      <nav className="sidebar-nav" aria-label="Primary navigation">
        {sections.map((section) => (
          <div key={section.title} className="sidebar-section">
            <p className="sidebar-section-title">{section.title}</p>
            <div className="sidebar-links">
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
                >
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
