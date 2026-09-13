import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import LibraryPage from "./pages/LibraryPage";
import PaperPage from "./pages/PaperPage";
import ProjectsPage from "./pages/ProjectsPage";
import "./styles.css";

function App() {
  return <BrowserRouter><Routes><Route path="/" element={<LibraryPage />} /><Route path="/projects" element={<ProjectsPage />} /><Route path="/papers/:paperId" element={<PaperPage />} /></Routes></BrowserRouter>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
