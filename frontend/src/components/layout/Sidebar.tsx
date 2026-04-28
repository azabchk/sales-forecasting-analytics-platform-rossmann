import React from "react";
import { NavLink } from "react-router-dom";

type SidebarItem = {
  to: string;
  label: string;
  icon: React.ReactNode;
};

type SidebarSection = {
  title: string;
  items: SidebarItem[];
};

type SidebarProps = {
  sections: SidebarSection[];
  isOpen: boolean;
  onClose: () => void;
};

export default function Sidebar({ sections, isOpen, onClose }: SidebarProps) {
  // Close sidebar on route change (mobile)
  const handleLinkClick = React.useCallback(() => {
    if (window.innerWidth < 980) onClose();
  }, [onClose]);

  // Close on Escape key
  React.useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape" && isOpen) onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  // Prevent body scroll when mobile sidebar is open
  React.useEffect(() => {
    if (isOpen && window.innerWidth < 980) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="sidebar-backdrop"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside className={`sidebar${isOpen ? " sidebar-open" : ""}`} aria-label="Primary navigation">
        <div className="sidebar-brand">
          <p className="sidebar-eyebrow">Sales Forecasting</p>
          <h1 className="sidebar-title">Rossmann Platform v2</h1>
          {/* Mobile close button */}
          <button
            className="sidebar-close-btn"
            type="button"
            aria-label="Close navigation"
            onClick={onClose}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
              <path d="M2 2L16 16M16 2L2 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <nav className="sidebar-nav">
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
                    onClick={handleLinkClick}
                  >
                    <span className="sidebar-link-icon" aria-hidden="true">{item.icon}</span>
                    <span className="sidebar-link-label">{item.label}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <p className="sidebar-footer-text">Aqiq Analytics Platform</p>
        </div>
      </aside>
    </>
  );
}
