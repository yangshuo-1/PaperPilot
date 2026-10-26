import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import "./paper-workspace.css";

export function TopNav() {
  return (
    <header className="topNav">
      <Link className="brandMark" to="/" aria-label="PaperPilot 首页">
        <img className="logo" src="/paper-vault-logo.svg" alt="" width={24} height={24} />
        <span>paper vault</span>
      </Link>
      <nav className="navLinks" aria-label="主导航">
        <NavLink to="/" end>
          Library
        </NavLink>
        <NavLink to="/projects">Projects</NavLink>
      </nav>
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="appShell">
      <a className="skipLink" href="#main-content">
        跳到主要内容
      </a>
      <TopNav />
      <div id="main-content" className="page appPage" tabIndex={-1}>
        {children}
      </div>
    </div>
  );
}
