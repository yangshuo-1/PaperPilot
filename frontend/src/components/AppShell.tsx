import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function TopNav() {
  return (
    <header className="topNav">
      <div className="brandMark">
        <img className="logo" src="/paper-vault-logo.svg" alt="paper vault logo" />
        paper vault
      </div>
      <nav className="navLinks">
        <Link to="/">Library</Link>
        <Link to="/projects">Projects</Link>
      </nav>
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return <div><TopNav /><div className="page">{children}</div></div>;
}
