import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { GlossaryProvider } from "./context/GlossaryContext";
import "./styles/tokens.css";
import "./styles/utilities.css";
import "./styles/print.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <GlossaryProvider>
        <App />
      </GlossaryProvider>
    </BrowserRouter>
  </StrictMode>,
);
